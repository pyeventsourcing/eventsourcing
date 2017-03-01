from tempfile import NamedTemporaryFile
from unittest import TestCase

from eventsourcing.infrastructure.datastore.sqlalchemy import SQLAlchemyDatastoreStrategy, SQLAlchemySettings
from eventsourcing.infrastructure.stored_event_repos.with_sqlalchemy import SQLAlchemyStoredEventRepository, \
    SqlStoredEvent


class SQLAlchemyRepoTestCase(TestCase):
    @property
    def stored_event_repo(self):
        try:
            return self._stored_event_repo
        except AttributeError:
            self.temp_file = NamedTemporaryFile('a')
            uri = 'sqlite:///' + self.temp_file.name
            datastore = SQLAlchemyDatastoreStrategy(
                settings=SQLAlchemySettings(uri=uri),
                tables=(SqlStoredEvent,),
            )
            datastore.setup_connection()
            datastore.setup_tables()

            stored_event_repo = SQLAlchemyStoredEventRepository(
                db_session=datastore.db_session,
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
