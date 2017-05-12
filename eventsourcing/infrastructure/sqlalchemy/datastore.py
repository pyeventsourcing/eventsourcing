import os

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative.api import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker

from eventsourcing.infrastructure.datastore import Datastore, DatastoreConnectionError, DatastoreSettings

ActiveRecord = declarative_base()

DEFAULT_SQLALCHEMY_DB_URI = 'sqlite:///:memory:'


class SQLAlchemySettings(DatastoreSettings):
    DB_URI = os.getenv('DB_URI', DEFAULT_SQLALCHEMY_DB_URI)

    def __init__(self, uri=DEFAULT_SQLALCHEMY_DB_URI):
        self.uri = uri or self.DB_URI


class SQLAlchemyDatastore(Datastore):

    def __init__(self, base=ActiveRecord, tables=None, connection_strategy='plain',
                 # connect_args=None, poolclass=None,
                 **kwargs):
        super(SQLAlchemyDatastore, self).__init__(**kwargs)
        self._session = None
        self._engine = None
        self._base = base
        self._tables = tables
        self._connection_strategy = connection_strategy
        # self._connect_args = connect_args
        # self._poolclass = poolclass

    def setup_connection(self):
        assert isinstance(self.settings, SQLAlchemySettings), self.settings
        # kwargs = {}
        # if self._connect_args is not None:
        #     kwargs['connect_args'] = self._connect_args
        # if self._poolclass is not None:
        #     kwargs['poolclass'] = self._poolclass
        self._engine = create_engine(
            self.settings.uri,
            strategy=self._connection_strategy,
            # **kwargs
        )

    def setup_tables(self):
        if self._tables is not None:
            for table in self._tables:
                table.__table__.create(self._engine, checkfirst=True)

    def drop_connection(self):
        if self._session:
            self._session.close()
        if self._engine:
            self._engine = None

    def drop_tables(self):
        if self._tables is not None:
            for table in self._tables:
                table.__table__.drop(self._engine, checkfirst=True)

    def truncate_tables(self):
        self.drop_tables()

    @property
    def session(self):
        if self._engine is None:
            raise DatastoreConnectionError("Need to call setup_connection() first")
        if self._session is None:
            session_factory = sessionmaker(bind=self._engine)
            self._session = scoped_session(session_factory)
        return self._session
