import datetime
from time import sleep, time
from unittest.case import TestCase
from uuid import uuid4

from eventsourcing.domain.model.entity import VersionedEntity, TimestampedEntity
from eventsourcing.domain.model.events import DomainEvent
from eventsourcing.utils.times import decimaltimestamp
from eventsourcing.utils.topic import get_topic
from eventsourcing.infrastructure.sequenceditem import SequencedItem
from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper


class Event1(VersionedEntity.Event):
    pass


class Event2(TimestampedEntity.Event):
    pass


class Event3(DomainEvent):
    pass


class ValueObject1(object):
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return self.__dict__ != other.__dict__


class TestSequencedItemMapper(TestCase):
    def test_with_versioned_entity_event(self):
        # Setup the mapper, and create an event.
        mapper = SequencedItemMapper(
            sequenced_item_class=SequencedItem,
            sequence_id_attr_name='originator_id',
            position_attr_name='originator_version'
        )
        entity_id1 = uuid4()
        event1 = Event1(originator_id=entity_id1, originator_version=101)

        # Check to_sequenced_item() method results in a sequenced item.
        sequenced_item = mapper.item_from_event(event1)
        self.assertIsInstance(sequenced_item, SequencedItem)
        self.assertEqual(sequenced_item.position, 101)
        self.assertEqual(sequenced_item.sequence_id, entity_id1)
        self.assertEqual(sequenced_item.topic, get_topic(Event1))
        self.assertTrue(sequenced_item.state)

        # Use the returned values to create a new sequenced item.
        sequenced_item_copy = SequencedItem(
            sequence_id=sequenced_item.sequence_id,
            position=sequenced_item.position,
            topic=sequenced_item.topic,
            state=sequenced_item.state,
        )

        # Check from_sequenced_item() returns an event.
        domain_event = mapper.event_from_item(sequenced_item_copy)
        self.assertIsInstance(domain_event, Event1)
        self.assertEqual(domain_event.originator_id, event1.originator_id)
        self.assertEqual(domain_event.originator_version, event1.originator_version)

    def test_with_timestamped_entity_event(self):
        # Setup the mapper, and create an event.
        mapper = SequencedItemMapper(
            sequenced_item_class=SequencedItem,
            sequence_id_attr_name='originator_id',
            position_attr_name='timestamp'
        )
        before = decimaltimestamp()
        sleep(0.000001)  # Avoid test failing due to timestamp having limited precision.
        event2 = Event2(originator_id='entity2')
        sleep(0.000001)  # Avoid test failing due to timestamp having limited precision.
        after = decimaltimestamp()

        # Check to_sequenced_item() method results in a sequenced item.
        sequenced_item = mapper.item_from_event(event2)
        self.assertIsInstance(sequenced_item, SequencedItem)
        self.assertGreater(sequenced_item.position, before)
        self.assertLess(sequenced_item.position, after)
        self.assertEqual(sequenced_item.sequence_id, 'entity2')
        self.assertEqual(sequenced_item.topic, get_topic(Event2))
        self.assertTrue(sequenced_item.state)

        # Use the returned values to create a new sequenced item.
        sequenced_item_copy = SequencedItem(
            sequence_id=sequenced_item.sequence_id,
            position=sequenced_item.position,
            topic=sequenced_item.topic,
            state=sequenced_item.state,
        )

        # Check from_sequenced_item() returns an event.
        domain_event = mapper.event_from_item(sequenced_item_copy)
        self.assertIsInstance(domain_event, Event2)
        self.assertEqual(domain_event.originator_id, event2.originator_id)
        self.assertEqual(domain_event.timestamp, event2.timestamp)

    def test_with_different_types_of_event_attributes(self):
        # Setup the mapper, and create an event.
        mapper = SequencedItemMapper(
            sequenced_item_class=SequencedItem,
            sequence_id_attr_name='originator_id',
            position_attr_name='a'
        )

        # Check value objects can be compared ok.
        self.assertEqual(ValueObject1('value1'), ValueObject1('value1'))
        self.assertNotEqual(ValueObject1('value1'), ValueObject1('value2'))

        # Create an event with dates and datetimes.
        event3 = Event3(
            originator_id='entity3',
            originator_version=303,
            a=datetime.datetime(2017, 3, 22, 9, 12, 14),
            b=datetime.date(2017, 3, 22),
            c=uuid4(),
            # d=Decimal(1.1),
            e=ValueObject1('value1'),
        )

        # Check to_sequenced_item() method results in a sequenced item.
        sequenced_item = mapper.item_from_event(event3)

        # Use the returned values to create a new sequenced item.
        sequenced_item_copy = SequencedItem(
            sequence_id=sequenced_item.sequence_id,
            position=sequenced_item.position,
            topic=sequenced_item.topic,
            state=sequenced_item.state,
        )

        # Check from_sequenced_item() returns an event.
        domain_event = mapper.event_from_item(sequenced_item_copy)
        self.assertIsInstance(domain_event, Event3)
        self.assertEqual(domain_event.originator_id, event3.originator_id)
        self.assertEqual(domain_event.a, event3.a)
        self.assertEqual(domain_event.b, event3.b)
        self.assertEqual(domain_event.c, event3.c)
        # self.assertEqual(domain_event.d, event3.d)
        self.assertEqual(domain_event.e, event3.e)
