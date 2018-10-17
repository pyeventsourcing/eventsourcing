from abc import abstractmethod

from eventsourcing.infrastructure.datastore import DatastoreConnectionError, DatastoreTableError
from eventsourcing.tests.base import AbstractTestCase


class AbstractDatastoreTestCase(AbstractTestCase):
    """
    Base class for test cases that use a datastore.
    """
    infrastructure_factory_class = None
    contiguous_record_ids = False

    def __init__(self, *args, **kwargs):
        super(AbstractDatastoreTestCase, self).__init__(*args, **kwargs)
        self._datastore = None
        self._factory = None

    def tearDown(self):
        self._datastore = None
        super(AbstractDatastoreTestCase, self).tearDown()

    @property
    def datastore(self):
        """
        :rtype: eventsourcing.infrastructure.datastore.datastore.Datastore
        """
        if self._datastore is None:
            self._datastore = self.construct_datastore()
        return self._datastore

    @abstractmethod
    def construct_datastore(self):
        """
        :rtype: eventsourcing.infrastructure.datastore.datastore.Datastore
        """

    @property
    def factory(self):
        if not self._factory:
            kwargs = {}
            if hasattr(self.datastore, 'session'):
                kwargs['session'] = self.datastore.session
            if self.contiguous_record_ids:
                kwargs['contiguous_record_ids'] = True
            self._factory = self.infrastructure_factory_class(**kwargs)
        return self._factory


class DatastoreTestCase(AbstractDatastoreTestCase):
    """
    Test case for datastore objects.
    """
    def test(self):

        # # Check the stored event class doesn't function before the connection is setup.
        # with self.assertRaises(DatastoreConnectionError):
        #     self.list_records()
        # with self.assertRaises(DatastoreConnectionError):
        #     self.create_record()

        # Setup the connection.
        self.datastore.setup_connection()

        # Check it doesn't matter if setup_connection() is called twice.
        self.datastore.setup_connection()

        # # Check the stored event class doesn't function before the tables are setup.
        # with self.assertRaises(DatastoreTableError):
        #     self.list_records()
        # with self.assertRaises(DatastoreTableError):
        #     self.create_record()

        # Setup the tables.
        self.datastore.setup_tables()

        # Check it doesn't matter if setup_tables() is called twice.
        self.datastore.setup_tables()

        # Check the stored event class does function after the tables have been setup.
        self.assertEqual(len(self.list_records()), 0)
        self.create_record()
        self.assertEqual(len(self.list_records()), 1)

        # Drop the tables.
        self.datastore.drop_tables()

        # Check the stored event class doesn't function after the tables have been dropped.
        with self.assertRaises(DatastoreTableError):
            self.list_records()
        with self.assertRaises(DatastoreTableError):
            self.create_record()

        # Drop the connection.
        self.datastore.close_connection()

    @abstractmethod
    def list_records(self):
        return []

    @abstractmethod
    def create_record(self):
        return None

    def tearDown(self):
        # Try to remove any tables.
        self.datastore.setup_connection()
        self.datastore.drop_tables()
        self.datastore.close_connection()
        super(DatastoreTestCase, self).tearDown()
