import json
import uuid
from abc import abstractmethod
from time import sleep
from typing import Tuple
from uuid import uuid4

from eventsourcing.application.policies import PersistencePolicy
from eventsourcing.domain.model.entity import VersionedEntity
from eventsourcing.domain.model.events import (
    EventWithOriginatorID,
    EventWithOriginatorVersion,
    EventWithTimestamp,
    LoggedEvent,
)
from eventsourcing.domain.model.snapshot import Snapshot
from eventsourcing.exceptions import (
    OperationalError,
    ProgrammingError,
    RecordConflictError,
)
from eventsourcing.infrastructure.base import (
    BaseRecordManager,
    EVENT_NOT_NOTIFIABLE,
    RecordManagerWithNotifications,
    RecordManagerWithTracking,
)
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.iterators import (
    SequencedItemIterator,
    ThreadedSequencedItemIterator,
)
from eventsourcing.infrastructure.sequenceditem import SequencedItem, StoredEvent
from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
from eventsourcing.tests.datastore_tests.base import AbstractDatastoreTestCase
from eventsourcing.utils.times import decimaltimestamp
from eventsourcing.utils.topic import get_topic


class RecordManagerTestCase(AbstractDatastoreTestCase):
    """
    Abstract test case for record managers.
    """

    EXAMPLE_EVENT_TOPIC1 = ""
    EXAMPLE_EVENT_TOPIC2 = ""

    def __init__(self, *args, **kwargs):
        super(RecordManagerTestCase, self).__init__(*args, **kwargs)
        self._record_manager = None

    def setUp(self):
        super(RecordManagerTestCase, self).setUp()
        if self.datastore is not None:
            self.datastore.setup_connection()
            try:
                self.datastore.setup_tables()
            except:
                self.datastore.drop_tables()
                self.datastore.setup_tables()

    def tearDown(self):
        self._record_manager = None
        if self.datastore is not None:
            self.datastore.drop_tables()
            self.datastore.close_connection()
        super(RecordManagerTestCase, self).tearDown()

    def test(self):
        sequence_id1 = uuid.uuid1()
        sequence_id2 = uuid.uuid1()

        # Check record manager returns empty list when there aren't any items.
        self.assertEqual(self.record_manager.list_items(sequence_id1), [])

        # Check record manager returns no sequence IDs.
        self.assertEqual([], self.record_manager.list_sequence_ids())

        position1, position2, position3 = self.construct_positions()

        self.assertLess(position1, position2)
        self.assertLess(position2, position3)

        # Append an item.
        state1 = json.dumps({"name": "value1"}).encode("utf-8")
        self.assertTrue(self.EXAMPLE_EVENT_TOPIC1)
        item1 = SequencedItem(
            sequence_id=sequence_id1,
            position=position1,
            topic=self.EXAMPLE_EVENT_TOPIC1,
            state=state1,
        )
        self.record_manager.record_item(item1)

        if self.record_manager.can_list_sequence_ids:
            # Check record manager returns one sequence ID.
            self.assertEqual([sequence_id1], self.record_manager.list_sequence_ids())

        # Append an item to a different sequence.
        state2 = json.dumps({"name": "value2"}).encode("utf-8")
        item2 = SequencedItem(
            sequence_id=sequence_id2,
            position=position1,
            topic=self.EXAMPLE_EVENT_TOPIC1,
            state=state2,
        )
        self.record_manager.record_item(item2)

        # Check record manager returns two sequence IDs.
        if self.record_manager.can_list_sequence_ids:
            self.assertEqual(
                sorted([sequence_id1, sequence_id2]),
                sorted(self.record_manager.list_sequence_ids()),
            )

        # Get first event.
        retrieved_item = self.record_manager.get_item(sequence_id1, position1)
        self.assertEqual(sequence_id1, retrieved_item.sequence_id)
        self.assertEqual(state1, retrieved_item.state)

        # Check index error is raised when item does not exist at position.
        with self.assertRaises(IndexError):
            self.record_manager.get_item(sequence_id1, position2)

        # Check record manager returns the item.
        retrieved_items = self.record_manager.list_items(sequence_id1)
        self.assertEqual(1, len(retrieved_items), str(retrieved_items))
        self.assertIsInstance(retrieved_items[0], SequencedItem)
        self.assertEqual(retrieved_items[0].sequence_id, item1.sequence_id)
        self.assertEqual(retrieved_items[0].state, item1.state)
        self.assertEqual(retrieved_items[0].topic, item1.topic)

        # Check raises RecordConflictError when appending an item at same position in same sequence.
        self.assertTrue(self.EXAMPLE_EVENT_TOPIC2)
        state3 = json.dumps({"name": "value3"}).encode("utf-8")
        item3 = SequencedItem(
            sequence_id=item1.sequence_id,
            position=position1,
            topic=self.EXAMPLE_EVENT_TOPIC2,
            state=state3,
        )
        self.assertEqual(item1.sequence_id, item3.sequence_id)
        self.assertNotEqual(item1.topic, item3.topic)
        self.assertNotEqual(item1.state, item3.state)
        # - append conflicting item as single item
        with self.assertRaises(RecordConflictError):
            self.record_manager.record_item(item3)

        item4 = SequencedItem(
            sequence_id=item1.sequence_id,
            position=position2,
            topic=self.EXAMPLE_EVENT_TOPIC2,
            state=state3,
        )
        item5 = SequencedItem(
            sequence_id=item1.sequence_id,
            position=position3,
            topic=self.EXAMPLE_EVENT_TOPIC2,
            state=state3,
        )
        # - append conflicting item in list with new items (none should be appended)
        with self.assertRaises(RecordConflictError):
            self.record_manager.record_items([item3, item4, item5])

        # Check there is still only one item.
        retrieved_items = self.record_manager.list_items(sequence_id1)
        self.assertEqual(len(retrieved_items), 1)

        # Check adding an empty list does nothing.
        self.record_manager.record_items([])
        retrieved_items = self.record_manager.list_items(sequence_id1)
        self.assertEqual(len(retrieved_items), 1)

        # Append a second and third item at the next positions.
        self.record_manager.record_items([item4, item5])

        # Check there are three items.
        retrieved_items = self.record_manager.list_items(sequence_id1)
        self.assertEqual(len(retrieved_items), 3)

        # Check the items are in sequential order.
        self.assertIsInstance(retrieved_items[0], SequencedItem)
        self.assertEqual(retrieved_items[0].sequence_id, item1.sequence_id)
        self.assertEqual(retrieved_items[0].topic, item1.topic)
        self.assertEqual(retrieved_items[0].state, item1.state)

        self.assertIsInstance(retrieved_items[1], SequencedItem)
        self.assertEqual(retrieved_items[1].sequence_id, item3.sequence_id)
        self.assertEqual(retrieved_items[1].topic, item4.topic)
        self.assertEqual(retrieved_items[1].state, item4.state)

        self.assertIsInstance(retrieved_items[2], SequencedItem)
        self.assertEqual(retrieved_items[2].sequence_id, item5.sequence_id)
        self.assertEqual(retrieved_items[2].topic, item5.topic)
        self.assertEqual(retrieved_items[2].state, item5.state)

        # Get items greater than a position.
        retrieved_items = self.record_manager.list_items(sequence_id1, gt=position1)
        self.assertEqual(len(retrieved_items), 2)
        self.assertEqual(retrieved_items[0].state, item4.state)
        self.assertEqual(retrieved_items[1].state, item5.state)

        # Get items greater then or equal to a position.
        retrieved_items = self.record_manager.list_items(sequence_id1, gte=position2)
        self.assertEqual(len(retrieved_items), 2)
        self.assertEqual(retrieved_items[0].state, item4.state)
        self.assertEqual(retrieved_items[1].state, item5.state)

        # Get items less than a position.
        if self.record_manager.can_lt_lte_get_records:
            retrieved_items = self.record_manager.list_items(sequence_id1, lt=position3)
            self.assertEqual(len(retrieved_items), 2)
            self.assertEqual(retrieved_items[0].state, item1.state)
            self.assertEqual(retrieved_items[1].state, item4.state)

        # Get items less then or equal to a position.
        if self.record_manager.can_lt_lte_get_records:
            retrieved_items = self.record_manager.list_items(
                sequence_id1, lte=position2
            )
            self.assertEqual(len(retrieved_items), 2)
            self.assertEqual(retrieved_items[0].state, item1.state)
            self.assertEqual(retrieved_items[1].state, item4.state)

        # Get items greater then or equal to a position and less then or equal to a position.
        if self.record_manager.can_lt_lte_get_records:
            retrieved_items = self.record_manager.list_items(
                sequence_id1, gte=position2, lte=position2
            )
            self.assertEqual(len(retrieved_items), 1)
            self.assertEqual(retrieved_items[0].state, item4.state)

        # Get items greater then or equal to a position and less then a position.
        if self.record_manager.can_lt_lte_get_records:
            retrieved_items = self.record_manager.list_items(
                sequence_id1, gte=position2, lt=position3
            )
            self.assertEqual(len(retrieved_items), 1)
            self.assertEqual(retrieved_items[0].state, item4.state)

        # Get items greater then a position and less then or equal to a position.
        if self.record_manager.can_lt_lte_get_records:
            retrieved_items = self.record_manager.list_items(
                sequence_id1, gt=position1, lte=position2
            )
            self.assertEqual(len(retrieved_items), 1)
            self.assertEqual(retrieved_items[0].state, item4.state)

        # Get items greater a position and less a position.
        if self.record_manager.can_lt_lte_get_records:
            retrieved_items = self.record_manager.list_items(
                sequence_id1, gt=position1, lt=position3
            )
            self.assertEqual(len(retrieved_items), 1)
            self.assertEqual(retrieved_items[0].state, item4.state)

        # Get items with a limit.
        if self.record_manager.can_limit_get_records:
            retrieved_items = self.record_manager.list_items(sequence_id1, limit=1)
            self.assertEqual(len(retrieved_items), 1)
            self.assertEqual(retrieved_items[0].state, item1.state)

        # Get items with a limit, and with descending query (so that we get the last ones).
        if self.record_manager.can_limit_get_records:
            retrieved_items = self.record_manager.list_items(
                sequence_id1, limit=2, query_ascending=False
            )
            self.assertEqual(2, len(retrieved_items))
            self.assertEqual(retrieved_items[0].state, item4.state)
            self.assertEqual(retrieved_items[1].state, item5.state)

        # Get items with a limit and descending query, greater than a position.
        if self.record_manager.can_limit_get_records:
            retrieved_items = self.record_manager.list_items(
                sequence_id1, limit=2, gt=position2, query_ascending=False
            )
            self.assertEqual(1, len(retrieved_items))
            self.assertEqual(retrieved_items[0].state, item5.state)

        # Get items with a limit and descending query, less than a position.
        if self.record_manager.can_limit_get_records:
            retrieved_items = self.record_manager.list_items(
                sequence_id1, limit=2, lt=position3, query_ascending=False
            )
            self.assertEqual(len(retrieved_items), 2)
            self.assertEqual(retrieved_items[0].state, item1.state)
            self.assertEqual(retrieved_items[1].state, item4.state)

        # Get items in descending order, queried in ascending order.
        retrieved_items = self.record_manager.list_items(
            sequence_id1, results_ascending=False
        )
        self.assertEqual(len(retrieved_items), 3)
        self.assertEqual(retrieved_items[0].state, item5.state)
        self.assertEqual(retrieved_items[2].state, item1.state)

        # Get items in descending order, queried in descending order.
        retrieved_items = self.record_manager.list_items(
            sequence_id1, query_ascending=False, results_ascending=False
        )
        self.assertEqual(len(retrieved_items), 3)
        self.assertEqual(retrieved_items[0].state, item5.state)
        self.assertEqual(retrieved_items[2].state, item1.state)

        # Check we can get all the sequence IDs.
        if self.record_manager.can_list_sequence_ids:
            sequence_ids = self.record_manager.list_sequence_ids()
            self.assertEqual(set(sequence_ids), {sequence_id1, sequence_id2})

            # Iterate over all items in all sequences.
            retrieved_items = []
            for sequence_id in sequence_ids:
                retrieved_items += self.record_manager.list_items(sequence_id)

            # Not always in order, but check the number of events.
            self.assertEqual(4, len(retrieved_items))

        # Delete some items.
        if self.record_manager.can_delete_records:
            records = list(self.record_manager.get_records(sequence_id1))
            self.assertTrue(len(records))
            for record in records:
                self.record_manager.delete_record(record)
            records = list(self.record_manager.get_records(sequence_id1))
            self.assertFalse(len(records))

        with self.assertRaises(RecordConflictError):
            self.record_manager.raise_sequenced_item_conflict()

        with self.assertRaises(IndexError):
            self.record_manager.raise_index_error(0)

        with self.assertRaises(RecordConflictError):
            self.record_manager.raise_record_integrity_error(Exception())

        with self.assertRaises(OperationalError):
            self.record_manager.raise_operational_error(Exception())

    @property
    def record_manager(self) -> BaseRecordManager:
        """
        :rtype: BaseRecordManager
        """
        if self._record_manager is None:
            self._record_manager = self.construct_record_manager()
        return self._record_manager

    @abstractmethod
    def construct_record_manager(self) -> BaseRecordManager:
        raise NotImplementedError()

    def construct_entity_record_manager(self, **kwargs):
        return self.factory.construct_integer_sequenced_record_manager(**kwargs)

    def construct_snapshot_record_manager(self):
        return self.factory.construct_snapshot_record_manager()

    def construct_timestamp_sequenced_record_manager(self):
        return self.factory.construct_timestamp_sequenced_record_manager()

    @abstractmethod
    def construct_positions(self) -> Tuple[int, int, int]:
        pass


class WithRecordManagers(AbstractDatastoreTestCase):
    """
    Base class for test cases that need a record manager.
    """

    drop_tables = False

    def __init__(self, *args, **kwargs):
        super(WithRecordManagers, self).__init__(*args, **kwargs)
        self._entity_record_manager = None
        self._log_record_manager = None
        self._snapshot_strategy = None

    def setUp(self):
        super(WithRecordManagers, self).setUp()
        if self.datastore:
            self.datastore.setup_connection()
            if self.drop_tables:
                self.datastore.drop_tables()
            self.datastore.setup_tables()

    def tearDown(self):
        self._log_record_manager = None
        self._entity_record_manager = None
        if self._datastore is not None:
            if self.drop_tables:
                self._datastore.drop_tables()
                self._datastore.close_connection()
                self._datastore = None
            else:
                self._datastore.truncate_tables()
        super(WithRecordManagers, self).tearDown()

    @property
    def entity_record_manager(self):
        if self._entity_record_manager is None:
            self._entity_record_manager = self.construct_entity_record_manager()
        return self._entity_record_manager

    @property
    def log_record_manager(self):
        if self._log_record_manager is None:
            self._log_record_manager = self.construct_log_record_manager()
        return self._log_record_manager

    @property
    def snapshot_record_manager(self):
        if self._snapshot_strategy is None:
            self._snapshot_strategy = self.construct_snapshot_record_manager()
        return self._snapshot_strategy

    def construct_entity_record_manager(self):
        return self.factory.construct_integer_sequenced_record_manager()

    def construct_log_record_manager(self):
        return self.factory.construct_timestamp_sequenced_record_manager()

    def construct_snapshot_record_manager(self):
        return self.factory.construct_snapshot_record_manager()


class VersionedEventExample1(EventWithOriginatorVersion, EventWithOriginatorID):
    pass


class VersionedEventExample2(EventWithOriginatorVersion, EventWithOriginatorID):
    pass


class TimestampedEventExample1(EventWithTimestamp, EventWithOriginatorID):
    pass


class TimestampedEventExample2(EventWithTimestamp, EventWithOriginatorID):
    pass


class TimestampSequencedItemTestCase(RecordManagerTestCase):
    """
    Abstract test case for timestamp sequenced record managers.
    """

    EXAMPLE_EVENT_TOPIC1 = get_topic(TimestampedEventExample1)
    EXAMPLE_EVENT_TOPIC2 = get_topic(TimestampedEventExample2)

    def construct_positions(self, num=3):
        while num:
            yield decimaltimestamp()
            num -= 1
            sleep(0.00001)

    def construct_record_manager(self):
        return self.factory.construct_timestamp_sequenced_record_manager()


class IntegerSequencedRecordTestCase(RecordManagerTestCase):
    """
    Abstract test case for integer sequenced record managers.
    """

    EXAMPLE_EVENT_TOPIC1 = get_topic(VersionedEventExample1)
    EXAMPLE_EVENT_TOPIC2 = get_topic(VersionedEventExample2)

    def construct_positions(self):
        return 0, 1, 2

    def construct_record_manager(self, **kwargs) -> BaseRecordManager:
        return self.factory.construct_integer_sequenced_record_manager(**kwargs)


class RecordManagerNotificationsTestCase(IntegerSequencedRecordTestCase):
    @property
    def record_manager(self) -> RecordManagerWithNotifications:
        record_manager = super().record_manager
        assert isinstance(record_manager, RecordManagerWithNotifications)
        return record_manager

    def test(self):
        sequence_id1 = uuid.uuid1()
        sequence_id2 = uuid.uuid1()

        old_notifications = list(self.record_manager.get_notification_records())

        max_notification_id = self.record_manager.get_max_notification_id()

        position1, position2, position3 = self.construct_positions()

        self.assertLess(position1, position2)
        self.assertLess(position2, position3)

        # Append an item.
        state1 = json.dumps({"name": "value1"}).encode("utf-8")
        self.assertTrue(self.EXAMPLE_EVENT_TOPIC1)
        item1 = SequencedItem(
            sequence_id=sequence_id1,
            position=position1,
            topic=self.EXAMPLE_EVENT_TOPIC1,
            state=state1,
        )
        self.record_manager.record_item(item1)

        self.assertEqual(
            max_notification_id + 1, self.record_manager.get_max_notification_id()
        )

        # Append an item to a different sequence.
        state2 = json.dumps({"name": "value2"}).encode("utf-8")
        item2 = SequencedItem(
            sequence_id=sequence_id2,
            position=position1,
            topic=self.EXAMPLE_EVENT_TOPIC1,
            state=state2,
        )
        self.record_manager.record_item(item2)

        self.assertEqual(
            max_notification_id + 2, self.record_manager.get_max_notification_id()
        )

        self.assertTrue(self.EXAMPLE_EVENT_TOPIC2)
        state3 = json.dumps({"name": "value3"}).encode("utf-8")

        item4 = SequencedItem(
            sequence_id=item1.sequence_id,
            position=position2,
            topic=self.EXAMPLE_EVENT_TOPIC2,
            state=state3,
        )
        item5 = SequencedItem(
            sequence_id=item1.sequence_id,
            position=position3,
            topic=self.EXAMPLE_EVENT_TOPIC2,
            state=state3,
        )

        # Append a second and third item at the next positions.
        self.record_manager.record_items([item4, item5])

        self.assertEqual(
            max_notification_id + 4, self.record_manager.get_max_notification_id()
        )

        # Check the record IDs are contiguous.
        records = list(self.record_manager.get_notification_records())
        len_old = len(old_notifications)
        self.assertEqual(len(records), 4 + len_old)
        first = None
        for i, record in enumerate(records):
            if first is None:
                first = record.id
            self.assertEqual(
                first + i,
                record.id,
                "Woops there's a gap: {}".format([r.id for r in records]),
            )

        # Resume from after the first event.
        retrieved_items = self.record_manager.get_notification_records(
            start=1 + len_old, stop=3 + len_old
        )
        retrieved_items = list(retrieved_items)
        self.assertEqual(len(retrieved_items), 2)
        self.assertEqual(retrieved_items[0].id, 2 + len_old)
        self.assertEqual(retrieved_items[1].id, 3 + len_old)


class RecordManagerTrackingRecordsTestCase(RecordManagerNotificationsTestCase):
    @property
    def record_manager(self) -> RecordManagerWithTracking:
        record_manager = super().record_manager
        assert isinstance(record_manager, RecordManagerWithTracking)
        return record_manager

    def create_factory_kwargs(self):
        kwargs = super().create_factory_kwargs()
        kwargs['application_name'] = 'app'
        return kwargs

    def test(self):
        sequence_id1 = uuid.uuid1()
        position1, position2, position3 = self.construct_positions()

        upstream_name = "upstream_app"
        self.assertEqual(
            self.record_manager.get_max_tracking_record_id(upstream_name), 0
        )
        self.assertFalse(self.record_manager.has_tracking_record(upstream_name, 0, 1))

        # Can write events with tracking kwargs.
        state1 = json.dumps({"name": "value1"}).encode("utf-8")
        self.assertTrue(self.EXAMPLE_EVENT_TOPIC1)
        item1 = SequencedItem(
            sequence_id=sequence_id1,
            position=position1,
            topic=self.EXAMPLE_EVENT_TOPIC1,
            state=state1,
        )
        tracking_kwargs1 = {
            "application_name": self.record_manager.application_name,
            "upstream_application_name": upstream_name,
            "pipeline_id": self.record_manager.pipeline_id,
            "notification_id": 1,
        }
        records1 = self.record_manager.to_records([item1])
        self.record_manager.write_records(
            tracking_kwargs=tracking_kwargs1, records=records1
        )
        self.assertEqual(
            self.record_manager.get_max_tracking_record_id(upstream_name), 1
        )
        self.assertTrue(self.record_manager.has_tracking_record(upstream_name, 0, 1))
        self.assertFalse(self.record_manager.has_tracking_record(upstream_name, 0, 2))

        # Can't write further events with same tracking kwargs.
        item2 = SequencedItem(
            sequence_id=sequence_id1,
            position=position2,
            topic=self.EXAMPLE_EVENT_TOPIC1,
            state=state1,
        )
        records2 = self.record_manager.to_records([item2])
        with self.assertRaises(RecordConflictError):
            self.record_manager.write_records(
                tracking_kwargs=tracking_kwargs1, records=records2
            )
        self.assertTrue(self.record_manager.has_tracking_record(upstream_name, 0, 1))
        self.assertFalse(self.record_manager.has_tracking_record(upstream_name, 0, 2))

        # Can write further events with different tracking kwargs.
        tracking_kwargs2 = {
            "application_name": self.record_manager.application_name,
            "upstream_application_name": upstream_name,
            "pipeline_id": self.record_manager.pipeline_id,
            "notification_id": 2,
        }
        self.record_manager.write_records(
            tracking_kwargs=tracking_kwargs2, records=records2
        )
        self.assertTrue(self.record_manager.has_tracking_record(upstream_name, 0, 1))
        self.assertTrue(self.record_manager.has_tracking_record(upstream_name, 0, 2))


class RecordManagerStoredEventsTestCase(RecordManagerTrackingRecordsTestCase):
    def create_factory_kwargs(self):
        kwargs = super().create_factory_kwargs()
        kwargs['sequenced_item_class'] = StoredEvent
        kwargs['application_name'] = 'app'
        return kwargs

    def test(self):
        """
        This test should use the "insert select max" mode,
        notification IDs aren't set in the fixtures.
        """
        sequence_id1 = uuid.uuid1()
        sequence_id2 = uuid.uuid1()

        old_notifications = list(self.record_manager.get_notification_records())

        max_notification_id = self.record_manager.get_max_notification_id()

        position1, position2, position3 = self.construct_positions()

        self.assertLess(position1, position2)
        self.assertLess(position2, position3)

        # Append an item.
        state1 = json.dumps({"name": "value1"}).encode("utf-8")
        self.assertTrue(self.EXAMPLE_EVENT_TOPIC1)
        item1 = StoredEvent(
            originator_id=sequence_id1,
            originator_version=position1,
            topic=self.EXAMPLE_EVENT_TOPIC1,
            state=state1,
        )
        self.record_manager.record_item(item1)

        self.assertEqual(
            max_notification_id + 1, self.record_manager.get_max_notification_id()
        )

        # Append an item to a different sequence.
        state2 = json.dumps({"name": "value2"}).encode("utf-8")
        item2 = StoredEvent(
            originator_id=sequence_id2,
            originator_version=position1,
            topic=self.EXAMPLE_EVENT_TOPIC1,
            state=state2,
        )
        self.record_manager.record_item(item2)

        self.assertEqual(
            max_notification_id + 2, self.record_manager.get_max_notification_id()
        )

        self.assertTrue(self.EXAMPLE_EVENT_TOPIC2)
        state3 = json.dumps({"name": "value3"}).encode("utf-8")
        item3 = StoredEvent(
            originator_id=item1.originator_id,
            originator_version=position2,
            topic=self.EXAMPLE_EVENT_TOPIC2,
            state=state3,
        )
        item4 = StoredEvent(
            originator_id=item1.originator_id,
            originator_version=position3,
            topic=self.EXAMPLE_EVENT_TOPIC2,
            state=state3,
        )

        # Append a second and third item at the next positions.
        self.record_manager.record_items([item3, item4])

        self.assertEqual(
            max_notification_id + 4, self.record_manager.get_max_notification_id()
        )

        # Check the record IDs are contiguous.
        records = list(self.record_manager.get_notification_records())
        len_old = len(old_notifications)
        self.assertEqual(len(records), 4 + len_old)
        first = None
        for i, record in enumerate(records):
            if first is None:
                first = record.notification_id
            self.assertEqual(
                first + i,
                record.notification_id,
                "Woops there's a gap: {}".format([r.notification_id for r in records]),
            )

    def test_insert_values(self):
        """
        This test should use the "insert values" mode,
        notification IDs are set in the records.
        """
        sequence_id1 = uuid.uuid1()
        sequence_id2 = uuid.uuid1()

        old_notifications = list(self.record_manager.get_notification_records())

        max_notification_id = self.record_manager.get_max_notification_id()

        position1, position2, position3 = self.construct_positions()

        self.assertLess(position1, position2)
        self.assertLess(position2, position3)

        # Append an item.
        state1 = json.dumps({"name": "value1"}).encode("utf-8")
        self.assertTrue(self.EXAMPLE_EVENT_TOPIC1)
        item1 = StoredEvent(
            originator_id=sequence_id1,
            originator_version=position1,
            topic=self.EXAMPLE_EVENT_TOPIC1,
            state=state1,
        )
        record1 = self.record_manager.to_record(item1)
        record1.notification_id = 1
        self.record_manager.write_records(records=[record1])

        self.assertEqual(
            max_notification_id + 1, self.record_manager.get_max_notification_id()
        )

        # Append an item to a different sequence.
        state2 = json.dumps({"name": "value2"}).encode("utf-8")
        item2 = StoredEvent(
            originator_id=sequence_id2,
            originator_version=position1,
            topic=self.EXAMPLE_EVENT_TOPIC1,
            state=state2,
        )
        record2 = self.record_manager.to_record(item2)
        record2.notification_id = 2
        self.record_manager.write_records(records=[record2])

        self.assertEqual(
            max_notification_id + 2, self.record_manager.get_max_notification_id()
        )

        self.assertTrue(self.EXAMPLE_EVENT_TOPIC2)
        state3 = json.dumps({"name": "value3"}).encode("utf-8")
        item3 = StoredEvent(
            originator_id=item1.originator_id,
            originator_version=position2,
            topic=self.EXAMPLE_EVENT_TOPIC2,
            state=state3,
        )
        item4 = StoredEvent(
            originator_id=item1.originator_id,
            originator_version=position3,
            topic=self.EXAMPLE_EVENT_TOPIC2,
            state=state3,
        )

        record4 = self.record_manager.to_record(item3)
        record4.notification_id = 3
        record5 = self.record_manager.to_record(item4)
        # Check we can't write a mixture with and without notification IDs.
        with self.assertRaises(ProgrammingError):
            self.record_manager.write_records(records=[record4, record5])
        record5.notification_id = 4
        self.record_manager.write_records(records=[record4, record5])

        self.assertEqual(
            max_notification_id + 4, self.record_manager.get_max_notification_id()
        )

        state4 = json.dumps({"name": "value3"}).encode("utf-8")
        item5 = StoredEvent(
            originator_id=item2.originator_id,
            originator_version=position2,
            topic=self.EXAMPLE_EVENT_TOPIC2,
            state=state4,
        )
        item6 = StoredEvent(
            originator_id=item2.originator_id,
            originator_version=position3,
            topic=self.EXAMPLE_EVENT_TOPIC2,
            state=state4,
        )

        record4 = self.record_manager.to_record(item5)
        record5 = self.record_manager.to_record(item6)
        record4.notification_id = None
        record5.notification_id = 5
        # Check we can't write a mixture with and without notification IDs.
        with self.assertRaises(ProgrammingError):
            self.record_manager.write_records(records=[record4, record5])

        # Check we can't write if notification ID isn't an integer.
        record4.notification_id = ''
        with self.assertRaises(ProgrammingError):
            self.record_manager.write_records(records=[record4, record5])

        # Check we can write events that are "not notifiable".
        record4.notification_id = EVENT_NOT_NOTIFIABLE
        self.record_manager.write_records(records=[record4, record5])

        self.assertEqual(
            max_notification_id + 5, self.record_manager.get_max_notification_id()
        )

        # Check the record IDs are contiguous.
        records = list(self.record_manager.get_notification_records())
        len_old = len(old_notifications)
        self.assertEqual(len(records), 5 + len_old)

        # Check the sixth record is the fifth notification (record4 not present).
        self.assertEqual(records[-1].originator_id, item2.originator_id)
        self.assertEqual(records[-1].originator_version, position3)

        first = None
        for i, record in enumerate(records):
            if first is None:
                first = record.notification_id
            self.assertEqual(
                first + i,
                record.notification_id,
                "Woops there's a gap: {}".format([r.notification_id for r in records]),
            )


class AbstractSequencedItemIteratorTestCase(WithRecordManagers):
    """
    Abstract test case for sequenced item iterators.
    """

    ENTITY_ID1 = uuid4()

    def test(self):
        self.setup_sequenced_items()

        assert isinstance(self.entity_record_manager, BaseRecordManager)
        stored_events = self.entity_record_manager.list_items(
            sequence_id=self.entity_id
        )
        stored_events = list(stored_events)
        self.assertEqual(len(stored_events), self.num_events)

        # # Check can get all events in ascending order.
        self.assert_iterator_yields_events(
            is_ascending=True,
            expect_at_start=self.sequenced_items[0].state,
            expect_at_end=self.sequenced_items[-1].state,
            expect_item_count=12,
            expect_page_count=3,
            expect_query_count=3,
            page_size=5,
        )

        # In descending order.
        self.assert_iterator_yields_events(
            is_ascending=False,
            expect_at_start=self.sequenced_items[-1].state,
            expect_at_end=self.sequenced_items[0].state,
            expect_item_count=12,
            expect_page_count=3,
            expect_query_count=3,
            page_size=5,
        )

        # Limit number of items.
        self.assert_iterator_yields_events(
            is_ascending=False,
            expect_at_start=self.sequenced_items[-1].state,
            expect_at_end=self.sequenced_items[-2].state,
            expect_item_count=2,
            expect_page_count=1,
            expect_query_count=1,
            page_size=5,
            limit=2,
        )

        # Match the page size to the number of events.
        self.assert_iterator_yields_events(
            is_ascending=True,
            expect_at_start=self.sequenced_items[0].state,
            expect_at_end=self.sequenced_items[-1].state,
            expect_item_count=12,
            expect_page_count=1,
            expect_query_count=2,
            page_size=self.num_events,
        )

        # Queries are minimised if we set a limit.
        self.assert_iterator_yields_events(
            is_ascending=True,
            expect_at_start=self.sequenced_items[0].state,
            expect_at_end=self.sequenced_items[-1].state,
            expect_item_count=12,
            expect_page_count=1,
            expect_query_count=1,
            page_size=self.num_events,
            limit=12,
        )

    def setup_sequenced_items(self):
        self.sequenced_items = []
        self.number_of_sequenced_items = 12
        for i in range(self.number_of_sequenced_items):
            state = (
                '{"i":%s,"entity_id":"%s","timestamp":%s}'
                % (i, self.entity_id, decimaltimestamp())
            ).encode("utf-8")
            sequenced_item = SequencedItem(
                sequence_id=self.entity_id,
                position=i,
                topic="eventsourcing.example.domain_model#Example.Created",
                state=state,
            )
            self.sequenced_items.append(sequenced_item)
            self.entity_record_manager.record_item(sequenced_item)

    def assert_iterator_yields_events(
        self,
        is_ascending,
        expect_at_start,
        expect_at_end,
        expect_item_count=1,
        expect_page_count=0,
        expect_query_count=0,
        page_size=1,
        limit=None,
    ):
        iterator = self.construct_iterator(is_ascending, page_size, limit=limit)
        retrieved_events = list(iterator)
        self.assertEqual(len(retrieved_events), expect_item_count, retrieved_events)
        self.assertEqual(iterator.page_counter, expect_page_count)
        self.assertEqual(iterator.query_counter, expect_query_count)
        self.assertEqual(iterator.all_item_counter, expect_item_count)
        self.assertEqual(expect_at_start, retrieved_events[0].state)
        self.assertEqual(expect_at_end, retrieved_events[-1].state)

    @property
    def entity_id(self):
        return self.ENTITY_ID1

    @property
    def num_events(self):
        return 12

    def construct_iterator(
        self, is_ascending, page_size, gt=None, lte=None, limit=None
    ):
        return self.iterator_cls(
            record_manager=self.entity_record_manager,
            sequence_id=self.entity_id,
            page_size=page_size,
            gt=gt,
            lte=lte,
            limit=limit,
            is_ascending=is_ascending,
        )

    @property
    @abstractmethod
    def iterator_cls(self):
        """
        Returns iterator class.
        """
        raise NotImplementedError()


class SequencedItemIteratorTestCase(AbstractSequencedItemIteratorTestCase):
    iterator_cls = SequencedItemIterator


class ThreadedSequencedItemIteratorTestCase(AbstractSequencedItemIteratorTestCase):
    iterator_cls = ThreadedSequencedItemIterator


class WithEventPersistence(WithRecordManagers):
    """
    Base class for test cases that need persistence policies.
    """

    def setUp(self):
        super(WithEventPersistence, self).setUp()
        # Setup the persistence subscriber.
        self.entity_event_store = EventStore(
            record_manager=self.entity_record_manager,
            event_mapper=SequencedItemMapper(
                sequenced_item_class=SequencedItem,
                sequence_id_attr_name="originator_id",
                position_attr_name="originator_version",
            ),
        )
        self.log_event_store = EventStore(
            record_manager=self.log_record_manager,
            event_mapper=SequencedItemMapper(
                sequenced_item_class=SequencedItem,
                sequence_id_attr_name="originator_id",
                position_attr_name="timestamp",
            ),
        )
        self.snapshot_store = EventStore(
            record_manager=self.snapshot_record_manager,
            event_mapper=SequencedItemMapper(
                sequenced_item_class=SequencedItem,
                sequence_id_attr_name="originator_id",
                position_attr_name="originator_version",
            ),
        )

        self.integer_sequenced_event_policy = None
        if self.entity_event_store is not None:
            self.integer_sequenced_event_policy = PersistencePolicy(
                event_store=self.entity_event_store,
                persist_event_type=VersionedEntity.Event,
            )

        self.timestamp_sequenced_event_policy = None
        if self.log_event_store is not None:
            self.timestamp_sequenced_event_policy = PersistencePolicy(
                event_store=self.log_event_store, persist_event_type=LoggedEvent
            )

        self.snapshot_policy = None
        if self.snapshot_store is not None:
            self.snapshot_policy = PersistencePolicy(
                event_store=self.snapshot_store, persist_event_type=Snapshot
            )

    def tearDown(self):
        # Close the persistence subscriber.
        if self.snapshot_policy:
            self.snapshot_policy.close()
        if self.timestamp_sequenced_event_policy:
            self.timestamp_sequenced_event_policy.close()
        if self.entity_event_store:
            self.integer_sequenced_event_policy.close()
        super(WithEventPersistence, self).tearDown()
