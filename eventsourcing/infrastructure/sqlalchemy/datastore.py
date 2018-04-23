import os

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import StaticPool

from eventsourcing.infrastructure.datastore import Datastore, DatastoreSettings
from eventsourcing.infrastructure.sqlalchemy.records import Base

DEFAULT_SQLALCHEMY_DB_URI = 'sqlite:///:memory:'
# DEFAULT_SQLALCHEMY_DB_URI = 'sqlite:///FILE_SYSTEM_PATH'
# DEFAULT_SQLALCHEMY_DB_URI = 'mysql://username:password@localhost/eventsourcing'
# DEFAULT_SQLALCHEMY_DB_URI = 'postgresql://username:password@localhost:5432/eventsourcing'


class SQLAlchemySettings(DatastoreSettings):
    def __init__(self, uri=None, pool_size=5):
        self.uri = uri or os.getenv('DB_URI', DEFAULT_SQLALCHEMY_DB_URI)
        self.pool_size = pool_size
        # self.pool_size = pool_size if not self.uri.startswith('sqlite') else 1


class SQLAlchemyDatastore(Datastore):

    def __init__(self, base=Base, tables=None, connection_strategy='plain',
                 session=None, **kwargs):
        super(SQLAlchemyDatastore, self).__init__(**kwargs)
        self._session = session
        self._engine = None
        self._base = base
        self._tables = tables
        self._connection_strategy = connection_strategy

    @property
    def session(self):
        if self._session is None:
            if self._engine is None:
                self.setup_connection()
            session_factory = sessionmaker(bind=self._engine)
            self._session = scoped_session(session_factory)
        return self._session

    def setup_connection(self):
        assert isinstance(self.settings, SQLAlchemySettings), self.settings
        if self._engine is None:
            if self.is_sqlite():
                kwargs = {
                    'connect_args': {'check_same_thread': False},
                }
            elif self.settings.pool_size == 1:
                kwargs = {
                    'poolclass': StaticPool
                }
            else:
                kwargs = {
                    'pool_size': self.settings.pool_size,
                }
            self._engine = create_engine(
                self.settings.uri,
                strategy=self._connection_strategy,
                **kwargs
            )

    def is_sqlite(self):
        return self.settings.uri.startswith('sqlite')

    def setup_tables(self, tables=None):
        if self._tables is not None:
            for table in self._tables:
                self.setup_table(table)

    def setup_table(self, table):
        table.__table__.create(self._engine, checkfirst=True)

    def drop_tables(self):
        if self._tables is not None:
            for table in self._tables:
                self.drop_table(table)

    def drop_table(self, table):
        table.__table__.drop(self._engine, checkfirst=True)

    def truncate_tables(self):
        self.drop_tables()

    def close_connection(self):
        if self._session:
            self._session.close()
            self._session = None
        if self._engine:
            # Call dispose(), unless sqlite (to avoid error 'stored_events'
            # table does not exist in projections.rst doc).
            if not self.is_sqlite():
                self._engine.dispose()
            self._engine = None
