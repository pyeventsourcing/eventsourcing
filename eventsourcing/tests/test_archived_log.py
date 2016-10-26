from eventsourcing.application.subscribers.persistence import PersistenceSubscriber
from eventsourcing.domain.model.archivedlog import ArchivedLog
from eventsourcing.domain.model.events import assert_event_handlers_empty
from eventsourcing.domain.services.eventstore import EventStore
from eventsourcing.infrastructure.event_sourced_repos.archivedlog_repo import ArchivedLogRepo
from eventsourcing.tests.unit_test_cases import AbstractTestCase
from eventsourcing.tests.unit_test_cases_cassandra import CassandraStoredEventRepoTestCase
from eventsourcing.tests.unit_test_cases_python_objects import PythonObjectsTestCase
from eventsourcing.tests.unit_test_cases_sqlalchemy import SQLAlchemyTestCase


class ArchivedLogTestCase(AbstractTestCase):
    @property
    def stored_event_repo(self):
        """
        Returns a stored event repository.

        Concrete log test cases will provide this method.
        """
        raise NotImplementedError

    def setUp(self):
        super(ArchivedLogTestCase, self).setUp()

        # Check we're starting clean, event handler-wise.
        assert_event_handlers_empty()

        # Setup the persistence subscriber.
        self.event_store = EventStore(self.stored_event_repo)
        self.persistence_subscriber = PersistenceSubscriber(event_store=self.event_store)

    def tearDown(self):

        # Close the persistence subscriber.
        self.persistence_subscriber.close()

        super(ArchivedLogTestCase, self).tearDown()

        # Check we finished clean, event handler-wise.
        assert_event_handlers_empty()

    def test_entity_lifecycle(self):

        archived_log_repo = ArchivedLogRepo(self.event_store)

        archived_log = archived_log_repo.get_or_create(log_name='log1', log_size=5)

        self.assertIsInstance(archived_log, ArchivedLog)

        item1 = 'item1'
        archived_log.add_item(item1)
        self.assertEqual(len(archived_log.items), 1)
        self.assertEqual(archived_log.items[0], item1)

        item2 = 'item2'
        archived_log.add_item(item2)
        self.assertEqual(len(archived_log.items), 2)
        self.assertEqual(archived_log.items[1], item2)

        archived_log.add_item(item2)
        archived_log.add_item(item2)
        archived_log.add_item(item2)

        self.assertEqual(len(archived_log.items), 0)



class TestArchivedLogWithCassandra(CassandraStoredEventRepoTestCase, ArchivedLogTestCase):
    pass


class TestArchivedLogWithPythonObjects(PythonObjectsTestCase, ArchivedLogTestCase):
    pass


class TestArchivedLogWithSQLAlchemy(SQLAlchemyTestCase, ArchivedLogTestCase):
    pass
