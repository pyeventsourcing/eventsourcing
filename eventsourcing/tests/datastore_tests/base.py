from abc import abstractmethod

from eventsourcing.infrastructure.datastore.base import DatastoreConnectionError, DatastoreTableError
from eventsourcing.tests.unit_test_cases import AbstractTestCase


class DatastoreStrategyTestCase(AbstractTestCase):

    def setUp(self):
        super(DatastoreStrategyTestCase, self).setUp()
        self.setup_datastore_strategy()

    def test(self):

        # Check the stored event class doesn't function before the connection is setup.
        with self.assertRaises(DatastoreConnectionError):
            self.list_records()
        with self.assertRaises(DatastoreConnectionError):
            self.create_record()

        # Setup the connection.
        self.strategy.setup_connection()

        # Check the stored event class doesn't function before the tables are setup.
        with self.assertRaises(DatastoreTableError):
            self.list_records()
        with self.assertRaises(DatastoreTableError):
            self.create_record()

        # Setup the tables.
        self.strategy.setup_tables()

        # Check the stored event class does function after the tables have been setup.
        self.assertEqual(len(self.list_records()), 0)
        self.create_record()
        self.assertEqual(len(self.list_records()), 1)

        # Drop the tables.
        self.strategy.drop_tables()

        # Check the stored event class doesn't function after the tables have been dropped.
        with self.assertRaises(DatastoreTableError):
            self.list_records()
        with self.assertRaises(DatastoreTableError):
            self.create_record()

        # Drop the tables.
        self.strategy.drop_connection()

        # Check the stored event class doesn't function after the connection has been dropped.
        with self.assertRaises(DatastoreConnectionError):
            self.list_records()
        with self.assertRaises(DatastoreConnectionError):
            self.create_record()

    @abstractmethod
    def setup_datastore_strategy(self):
        self.strategy = None

    @abstractmethod
    def list_records(self):
        return []

    @abstractmethod
    def create_record(self):
        return None
