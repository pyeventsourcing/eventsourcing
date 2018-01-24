import os

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from eventsourcing.infrastructure.datastore import Datastore, DatastoreSettings
from eventsourcing.infrastructure.sqlalchemy.records import Base

DEFAULT_SQLALCHEMY_DB_URI = 'sqlite:///:memory:'
# DEFAULT_SQLALCHEMY_DB_URI = 'sqlite:///FILE_SYSTEM_PATH'
# DEFAULT_SQLALCHEMY_DB_URI = 'mysql://username:password@localhost/eventsourcing'
# DEFAULT_SQLALCHEMY_DB_URI = 'postgresql://username:password@localhost:5432/eventsourcing'


class SQLAlchemySettings(DatastoreSettings):
    def __init__(self, uri=None):
        self.uri = uri or os.getenv('DB_URI', DEFAULT_SQLALCHEMY_DB_URI)


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
            self._engine = create_engine(
                self.settings.uri,
                strategy=self._connection_strategy,
            )

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
            self._engine = None
