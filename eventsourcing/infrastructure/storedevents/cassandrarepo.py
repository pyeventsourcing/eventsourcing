from random import random
from time import sleep

import six
from cassandra import DriverException
from cassandra.cqlengine.models import Model, columns
from cassandra.cqlengine.query import LWTException

from eventsourcing.exceptions import ConcurrencyError, EntityVersionDoesNotExist
from eventsourcing.infrastructure.eventstore import AbstractStoredEventRepository
from eventsourcing.infrastructure.storedevents.threaded_iterator import ThreadedStoredEventIterator
from eventsourcing.infrastructure.transcoding import EntityVersion


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
    def __init__(self, stored_event_table, **kwargs):
        super(CassandraStoredEventRepository, self).__init__(**kwargs)
        self.stored_event_table = stored_event_table

    @property
    def iterator_class(self):
        return ThreadedStoredEventIterator

    def write_version_and_event(self, new_stored_event, new_version_number=None, max_retries=3,
                                artificial_failure_rate=0):
        """
        Writes entity version if not exists, and then writes the stored event.
        """
        # Write the next version.
        stored_entity_id = new_stored_event.stored_entity_id
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

        # Write the stored event into the database.
        # try:
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

            except DriverException:

                if retries <= 0:
                    # Raise the error after retries exhausted.
                    raise
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
        #         CqlStoredEvent.get(n=new_stored_event.stored_entity_id, v=new_stored_event.event_id)
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
        #                         raise Exception("Unable to delete version {} of entity {} after failing to write"
        #                                         "event: event write error {}: version delete error {}"
        #                                         .format(new_entity_version, stored_entity_id,
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
            raise EntityVersionDoesNotExist()
        assert isinstance(cql_entity_version, CqlEntityVersion)
        return EntityVersion(
            entity_version_id=entity_version_id,
            event_id=cql_entity_version.v,
        )

    def get_entity_events(self, stored_entity_id, after=None, until=None, limit=None, query_ascending=True,
                          results_ascending=True, include_after_when_ascending=False,
                          include_until_when_descending=False):

        # Todo: Extend unit test to make sure limit is effective when less than 1.
        assert limit is None or limit >= 1, limit
        # if limit is not None and limit < 1:
        #     return []

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

    def to_cql(self, stored_event):
        assert isinstance(stored_event, self.stored_event_class), stored_event
        return self.stored_event_table(
            n=stored_event.stored_entity_id,
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
