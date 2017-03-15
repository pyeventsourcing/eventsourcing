from random import random
from time import sleep

import six
from cassandra import DriverException
from cassandra.cqlengine.models import Model, columns
from cassandra.cqlengine.query import LWTException

from eventsourcing.exceptions import ConcurrencyError, DatasourceOperationError, SequencedItemError, \
    TimeSequenceError
from eventsourcing.infrastructure.eventstore import AbstractStoredEventRepository
from eventsourcing.infrastructure.storedevents.activerecord import AbstractActiveRecordStrategy
from eventsourcing.infrastructure.storedevents.threaded_iterator import ThreadedSequencedItemIterator
from eventsourcing.infrastructure.transcoding import EntityVersion


class CassandraActiveRecordStrategy(AbstractActiveRecordStrategy):

    def get_items(self, sequence_id, gt=None, gte=None, lt=None, lte=None, limit=None,
                  query_ascending=True, results_ascending=True):

        assert limit is None or limit >= 1, limit
        assert not (gte and gt)
        assert not (lte and lt)

        query = self.filter(s=sequence_id)

        if query_ascending:
            query = query.order_by('p')

        if gt is not None:
            query = query.filter(p__gt=gt)
        if gte is not None:
            query = query.filter(p__gte=gte)
        if lt is not None:
            query = query.filter(p__lt=lt)
        if lte is not None:
            query = query.filter(p__lte=lte)

        if limit is not None:
            query = query.limit(limit)

        items = six.moves.map(self.from_active_record, query)

        items = list(items)

        if results_ascending != query_ascending:
            items.reverse()

        return items

    def append_item(self, item):
        active_record = self.to_active_record(item)
        try:
            active_record.save()
        except LWTException as e:
            raise SequencedItemError((active_record.s, active_record.p, e))
        except DriverException as e:
            raise DatasourceOperationError(e)

    def to_active_record(self, sequenced_item):
        """
        Returns an active record instance, from given sequenced item.
        """
        assert isinstance(sequenced_item, self.sequenced_item_class), (type(sequenced_item), self.sequenced_item_class)
        return self.active_record_class(
            s=sequenced_item.sequence_id,
            p=sequenced_item.position,
            t=sequenced_item.topic,
            d=sequenced_item.data
        )

    def from_active_record(self, active_record):
        """
        Returns a sequenced item instance, from given active record.
        """
        return self.sequenced_item_class(
            sequence_id=active_record.s,
            position=active_record.p,
            topic=active_record.t,
            data=active_record.d,
        )

    def filter(self, *args, **kwargs):
        return self.active_record_class.objects.filter(*args, **kwargs)


class CqlEntityVersion(Model):
    """Stores the stored entity ID and entity version as a partition key."""

    __table_name__ = 'entity_versions'

    # Makes sure we can't write the same version twice,
    # helps to implement optimistic concurrency control.
    _if_not_exists = True

    # Entity-version identifier (a string).
    r = columns.Text(partition_key=True)

    # Stored event ID (normally a uuid1().hex).
    v = columns.Text()

    # Because models with one column break Cassandra driver 3.5.0.
    x = columns.Text(default='')


class CqlIntegerSequencedItem(Model):
    """Stores integer-sequenced items in Cassandra."""

    _if_not_exists = True

    __table_name__ = 'integer_sequenced_items'

    # Sequence ID (e.g. an entity or aggregate ID).
    s = columns.Text(partition_key=True)

    # Position (index) of item in sequence.
    p = columns.BigInt(clustering_order='DESC', primary_key=True)

    # Topic of the item (e.g. path to domain event class).
    t = columns.Text(required=True)

    # State of the item (serialized dict, possibly encrypted).
    d = columns.Text(required=True)


class CqlTimestampSequencedItem(Model):
    """Stores timestamp-sequenced items in Cassandra."""

    _if_not_exists = True

    __table_name__ = 'timestamp_sequenced_items'

    # Sequence ID (e.g. an entity or aggregate ID).
    s = columns.Text(partition_key=True)

    # Position (in time) of item in sequence.
    # p = columns.TimeUUID(clustering_order='DESC', primary_key=True)
    p = columns.Double(clustering_order='DESC', primary_key=True)

    # Topic of the item (e.g. path to domain event class).
    t = columns.Text(required=True)

    # State of the item (serialized dict, possibly encrypted).
    d = columns.Text(required=True)


class CqlTimeuuidSequencedItem(Model):
    """Stores timeuuid-sequenced items in Cassandra."""

    _if_not_exists = True

    __table_name__ = 'timeuuid_sequenced_items'

    # Sequence ID (e.g. an entity or aggregate ID).
    s = columns.Text(partition_key=True)

    # Position (in time) of item in sequence.
    p = columns.TimeUUID(clustering_order='DESC', primary_key=True)

    # Topic of the item (e.g. path to domain event class).
    t = columns.Text(required=True)

    # State of the item (serialized dict, possibly encrypted).
    d = columns.Text(required=True)


class CqlStoredEvent(Model):
    __table_name__ = 'storedevents'

    # Stored entity ID (normally a string, with the entity type name at the start)
    n = columns.Text(partition_key=True)

    # Stored event ID (normally a UUID1)
    v = columns.TimeUUID(clustering_order='DESC', primary_key=True)

    # Stored event topic (path to the event object class)
    t = columns.Text(required=True)

    # Stored event attributes (the entity object __dict__)
    a = columns.Text(required=True)


class CassandraStoredEventRepository(AbstractStoredEventRepository):
    def __init__(self, stored_event_table=None, integer_sequenced_item_table=None, time_sequenced_item_table=None,
                 **kwargs):
        super(CassandraStoredEventRepository, self).__init__(**kwargs)
        self.stored_event_table = stored_event_table
        self.integer_sequenced_item_table = integer_sequenced_item_table
        self.time_sequenced_item_table = time_sequenced_item_table

    @property
    def iterator_class(self):
        return ThreadedSequencedItemIterator

    def append_time_sequenced_item(self, item):
        cql_object = self.to_cql_time_sequenced_item(item)
        try:
            cql_object.save()
        except LWTException:
            raise TimeSequenceError((cql_object.s, cql_object.p))
        except DriverException as e:
            raise DatasourceOperationError(e)

    def write_version_and_event(self, new_stored_event, new_version_number=None, max_retries=3,
                                artificial_failure_rate=0):
        """
        Writes entity version if not exists, and then writes the stored event.
        """

        # Write the next version.
        stored_entity_id = new_stored_event.entity_id
        new_entity_version = None
        if self.always_write_entity_version and new_version_number is not None:
            assert isinstance(new_version_number, six.integer_types)
            #  - uses the "if not exists" optimistic concurrency control feature
            #    of Cassandra, hence this operation is assumed to succeed only once
            new_entity_version_id = self.make_entity_version_id(stored_entity_id, new_version_number)
            new_entity_version = CqlEntityVersion(
                r=new_entity_version_id,
                v=new_stored_event.event_id,
            )
            try:
                new_entity_version.save()
            except LWTException as e:
                raise ConcurrencyError(
                    "Version {} of entity {} already exists: {}".format(new_entity_version, stored_entity_id, e))

        # Increased latency here causes increased contention.
        #  - used for testing concurrency exceptions
        if artificial_failure_rate:
            sleep(artificial_failure_rate)

        # Write the item into the database.
        retries = max_retries
        while True:
            try:
                # Instantiate a Cassandra CQL engine object.
                cql_stored_event = self.to_cql(new_stored_event)

                # Optionally mimic an unreliable save() operation.
                #  - used for testing retries
                if artificial_failure_rate and (random() > 1 - artificial_failure_rate):
                    raise DriverException("Artificial failure")

                # Save the event.
                cql_stored_event.save()

            except DriverException as e:

                if retries <= 0:
                    if new_entity_version is not None:
                        # Delete the new entity version.
                        new_entity_version.delete()

                    # Raise the error after retries exhausted.
                    raise DatasourceOperationError(e)
                else:
                    # Otherwise retry.
                    retries -= 1
                    sleep(0.05 + 0.1 * random())
            else:
                break

                # except DriverException as event_write_error:
                #     # If we get here, we're in trouble because the version has been
                #     # written, but perhaps not the event, so the entity may be broken
                #     # because it might not be possible to get the entity with version
                #     # number high enough to pass the optimistic concurrency check
                #     # when storing subsequent events.
                #
                #     # Back off for a little bit.
                #     sleep(0.1)
                #     try:
                #         # If the event actually exists, despite the exception, all is well.
                #         CqlStoredEvent.get(n=new_stored_event.entity_id, v=new_stored_event.event_id)
                #
                #     except CqlStoredEvent.DoesNotExist:
                #         # Otherwise, try harder to recover by removing the new version.
                #         if new_entity_version is not None:
                #             retries = max_retries * 3
                #             while True:
                #                 try:
                #                     # Optionally mimic an unreliable delete() operation.
                #                     #  - used for testing retries
                #                     if artificial_failure_rate and (random() > 1 - artificial_failure_rate):
                #                         raise DriverException("Artificial failure")
                #
                #                     # Delete the new entity version.
                #                     new_entity_version.delete()
                #
                #                 except DriverException as version_delete_error:
                #                     # It's not going very well, so maybe retry.
                #                     if retries <= 0:
                #                         # Raise when retries are exhausted.
                #                         raise Exception("Unable to delete version {} of entity {} after failing to
                #  write"
                #                                         "event: event write error {}: version delete error {}"
                #                                         .format(new_entity_version, entity_id,
                #                                                 event_write_error, version_delete_error))
                #                     else:
                #                         # Otherwise retry.
                #                         retries -= 1
                #                         sleep(0.05 + 0.1 * random())
                #                 else:
                #                     # The entity version was deleted, all is well.
                #                     break
                #         raise event_write_error

    def get_entity_version(self, stored_entity_id, version_number):
        entity_version_id = self.make_entity_version_id(stored_entity_id, version_number)
        try:
            cql_entity_version = CqlEntityVersion.get(r=entity_version_id)
        except CqlEntityVersion.DoesNotExist:
            self.raise_entity_version_not_found(stored_entity_id, version_number)
        else:
            assert isinstance(cql_entity_version, CqlEntityVersion)
            return EntityVersion(
                entity_version_id=entity_version_id,
                event_id=cql_entity_version.v,
            )

    def get_stored_events(self, stored_entity_id, after=None, until=None, limit=None, query_ascending=True,
                          results_ascending=True, include_after_when_ascending=False,
                          include_until_when_descending=False):

        assert limit is None or limit >= 1, limit

        query = self.stored_event_table.objects.filter(n=stored_entity_id)

        if query_ascending:
            query = query.order_by('v')

        if after is not None:
            if query_ascending and not include_after_when_ascending:
                query = query.filter(v__gt=after)
            else:
                query = query.filter(v__gte=after)
        if until is not None:
            if query_ascending or include_until_when_descending:
                query = query.filter(v__lte=until)
            else:
                query = query.filter(v__lt=until)

        if limit is not None:
            query = query.limit(limit)

        events = self.map(self.from_cql, query)
        events = list(events)

        if results_ascending != query_ascending:
            events.reverse()

        return events

    def get_time_sequenced_items(self, sequence_id, gt=None, gte=None, lt=None, lte=None, limit=None,
                                 query_ascending=True, results_ascending=True):

        assert limit is None or limit >= 1, limit

        query = self.time_sequenced_item_table.objects.filter(s=sequence_id)

        if query_ascending:
            query = query.order_by('p')

        if gt is not None:
            query = query.filter(p__gt=gt)
        if gte is not None:
            query = query.filter(p__gte=gte)
        if lt is not None:
            query = query.filter(p__lt=lt)
        if lte is not None:
            query = query.filter(p__lte=lte)

        if limit is not None:
            query = query.limit(limit)

        events = self.map(self.from_cql_time_sequenced_item, query)
        events = list(events)

        if results_ascending != query_ascending:
            events.reverse()

        return events

    def to_cql(self, stored_event):
        assert isinstance(stored_event, self.stored_event_class), stored_event
        return self.stored_event_table(
            n=stored_event.entity_id,
            v=stored_event.event_id,
            t=stored_event.event_topic,
            a=stored_event.event_attrs
        )

    def from_cql(self, cql_stored_event):
        assert isinstance(cql_stored_event, CqlStoredEvent), cql_stored_event
        return self.stored_event_class(
            stored_entity_id=cql_stored_event.n,
            event_id=cql_stored_event.v.hex,
            event_topic=cql_stored_event.t,
            event_attrs=cql_stored_event.a
        )

    def to_cql_time_sequenced_item(self, item):
        assert isinstance(item, self.sequenced_item_type), item
        return self.time_sequenced_item_table(
            s=item.sequence_id,
            p=item.position,
            t=item.topic,
            d=item.data
        )

    def from_cql_time_sequenced_item(self, cql_item):
        assert isinstance(cql_item, self.time_sequenced_item_table), cql_item
        return self.sequenced_item_type(
            sequence_id=cql_item.s,
            position=cql_item.p.hex,
            topic=cql_item.t,
            data=cql_item.d
        )
