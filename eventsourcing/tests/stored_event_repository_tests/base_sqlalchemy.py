from tempfile import NamedTemporaryFile

from eventsourcing.infrastructure.datastore.sqlalchemy import SQLAlchemyDatastoreStrategy, SQLAlchemySettings
from eventsourcing.infrastructure.stored_event_repos.with_sqlalchemy import SQLAlchemyStoredEventRepository, \
    SqlStoredEvent
from eventsourcing.tests.base import AbstractTestCase
from eventsourcing.tests.stored_event_repository_tests.base import AbstractStoredEventRepositoryTestCase


class SQLAlchemyTestCase(AbstractTestCase):
    """
    Uses the datastore object to set up connection and tables with SQLAlchemy.

    """
    def setUp(self):
        super(SQLAlchemyTestCase, self).setUp()
        # Setup the keyspace and column family for stored events.
        self.datastore.setup_tables()

    def tearDown(self):
        # Drop the keyspace.
        self.datastore.drop_tables()
        self.datastore.drop_connection()
        del(self._datastore)  # Todo: Refactor this...
        super(SQLAlchemyTestCase, self).tearDown()

    @property
    def datastore(self):
        try:
            return self._datastore
        except AttributeError:
            self.temp_file = NamedTemporaryFile('a')
            uri = 'sqlite:///' + self.temp_file.name
            self._datastore = SQLAlchemyDatastoreStrategy(
                settings=SQLAlchemySettings(uri=uri),
                tables=(SqlStoredEvent,),
            )
            self._datastore.setup_connection()
        return self._datastore


class SQLAlchemyRepoTestCase(SQLAlchemyTestCase, AbstractStoredEventRepositoryTestCase):
    @property
    def stored_event_repo(self):
        """
        Implements the stored_event_repo property, by
        providing a SQLAlchemy stored event repository.
        """
        try:
            return self._stored_event_repo
        except AttributeError:
            stored_event_repo = SQLAlchemyStoredEventRepository(
                db_session=self.datastore.db_session,
                stored_event_table=SqlStoredEvent,
                always_check_expected_version=True,
                always_write_entity_version=True,
            )
            self._stored_event_repo = stored_event_repo
        return self._stored_event_repo

    def tearDown(self):
        # Unlink temporary file.
        if self.temp_file:
            self.temp_file.close()
        super(SQLAlchemyRepoTestCase, self).tearDown()
