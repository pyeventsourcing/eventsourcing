import os

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative.api import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker

from eventsourcing.infrastructure.datastore.base import DatastoreSettings, Datastore, DatastoreConnectionError

Base = declarative_base()


DEFAULT_SQLALCHEMY_DB_URI = 'sqlite:///:memory:'


class SQLAlchemySettings(DatastoreSettings):
    DB_URI = os.getenv('DB_URI', DEFAULT_SQLALCHEMY_DB_URI)

    def __init__(self, uri=DEFAULT_SQLALCHEMY_DB_URI):
        self.uri = uri or self.DB_URI


class SQLAlchemyDatastore(Datastore):

    def __init__(self, **kwargs):
        super(SQLAlchemyDatastore, self).__init__(**kwargs)
        self._db_session = None
        self._engine = None

    def setup_connection(self):
        assert isinstance(self.settings, SQLAlchemySettings), self.settings
        self._engine = create_engine(self.settings.uri, strategy='threadlocal')

    def setup_tables(self):
        Base.metadata.create_all(self._engine)

    def drop_connection(self):
        if self._db_session:
            self._db_session.close()
        if self._engine:
            self._engine = None

    def drop_tables(self):
        Base.metadata.drop_all(self._engine)

    @property
    def db_session(self):
        if self._engine is None:
            raise DatastoreConnectionError("Need to call setup_connection() first")
        if self._db_session is None:
            session_factory = sessionmaker(bind=self._engine)
            self._db_session = scoped_session(session_factory)
        return self._db_session
