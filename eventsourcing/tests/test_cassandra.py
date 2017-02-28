from unittest import TestCase
from uuid import uuid1

from cassandra import InvalidRequest
from cassandra.cluster import NoHostAvailable
from cassandra.cqlengine import CQLEngineException

from eventsourcing.infrastructure.stored_event_repos.with_cassandra import CqlStoredEvent
from eventsourcing.infrastructure.cassandra import CassandraDatastoreStrategy, CassandraSettings


class TestCassandraDatastoreStrategy(TestCase):

    def test(self):
        # Setup the strategy.
        strategy = CassandraDatastoreStrategy(
            settings=CassandraSettings(
                default_keyspace='eventsourcing_testing'
            ),
            tables=(CqlStoredEvent,),
        )

        # Check the stored event class doesn't function before the connection is setup.
        with self.assertRaises(CQLEngineException):
            self.list_records()
        with self.assertRaises(CQLEngineException):
            self.create_record()

        # Setup the connection.
        strategy.setup_connection()

        # Check the stored event class doesn't function before the tables are setup.
        with self.assertRaises(InvalidRequest):
            self.list_records()
        with self.assertRaises(InvalidRequest):
            self.create_record()

        # Setup the tables.
        strategy.setup_tables()

        # Check the stored event class does function after the tables have been setup.
        self.assertEqual(len(self.list_records()), 0)
        self.create_record()
        self.assertEqual(len(self.list_records()), 1)

        # Drop the tables.
        strategy.drop_tables()

        # Check the stored event class doesn't function after the tables have been dropped.
        with self.assertRaises(InvalidRequest):
            self.list_records()
        with self.assertRaises(InvalidRequest):
            self.create_record()

        # Drop the tables.
        strategy.drop_connection()

        # Check the stored event class doesn't function after the connection has been dropped.
        with self.assertRaises(NoHostAvailable):
            self.list_records()
        with self.assertRaises(NoHostAvailable):
            self.create_record()

    def list_records(self):
        return list(CqlStoredEvent.objects.all())

    def create_record(self):
        record = CqlStoredEvent(n='entity1', v=uuid1(), t='topic', a='{}')
        record.save()
        return record
