from tempfile import NamedTemporaryFile
from unittest import TestCase

from eventsourcing.infrastructure.stored_event_repos.with_sqlalchemy import get_scoped_session_facade, \
    SQLAlchemyStoredEventRepository


class SQLAlchemyTestCase(TestCase):

    @property
    def stored_event_repo(self):
        try:
            return self._stored_event_repo
        except AttributeError:
            self.temp_file = NamedTemporaryFile('a')
            uri = 'sqlite:///' + self.temp_file.name
            scoped_session_facade = get_scoped_session_facade(uri)
            stored_event_repo = SQLAlchemyStoredEventRepository(scoped_session_facade)
            self._stored_event_repo = stored_event_repo
            return self._stored_event_repo

    def tearDown(self):
        # Unlink temporary file.
        if self.temp_file:
            self.temp_file.close()
        super(SQLAlchemyTestCase, self).tearDown()