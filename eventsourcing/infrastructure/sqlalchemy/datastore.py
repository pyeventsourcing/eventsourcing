import os
from typing import Optional, Union, Sequence, Any, Dict

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import InternalError
from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy.orm import scoped_session, sessionmaker, Session
from sqlalchemy.pool import StaticPool

from eventsourcing.infrastructure.datastore import AbstractDatastore, DatastoreSettings
from eventsourcing.infrastructure.sqlalchemy.records import Base

SQLITE_IN_MEMORY = "sqlite:///:memory:"
DEFAULT_SQLALCHEMY_DB_URI = SQLITE_IN_MEMORY
# DEFAULT_SQLALCHEMY_DB_URI = 'sqlite:///FILE_SYSTEM_PATH'
# DEFAULT_SQLALCHEMY_DB_URI = 'mysql://username:password@localhost/eventsourcing'
# DEFAULT_SQLALCHEMY_DB_URI = 'postgresql://username:password@localhost:5432/eventsourcing'
DEFAULT_SQLALCHEMY_DB_POOL_SIZE = 5


class SQLAlchemySettings(DatastoreSettings):
    def __init__(self, uri: Optional[str] = None, pool_size: Optional[int] = None):
        if uri is not None:
            self.uri = uri
        else:
            self.uri = os.getenv("DB_URI", DEFAULT_SQLALCHEMY_DB_URI)
        if pool_size is not None:
            self.pool_size = pool_size
        else:
            self.pool_size = int(
                os.getenv("DB_POOL_SIZE", DEFAULT_SQLALCHEMY_DB_POOL_SIZE)
            )


class SQLAlchemyDatastore(AbstractDatastore[SQLAlchemySettings]):
    def __init__(
        self,
        settings: SQLAlchemySettings,
        base: DeclarativeMeta = Base,
        tables: Optional[Sequence] = None,
        connection_strategy: str = "plain",
        session: Optional[Union[Session, scoped_session]] = None,
    ):
        super(SQLAlchemyDatastore, self).__init__(settings=settings)
        self._was_session_created_here = False
        self._session = session
        if session:
            self._engine: Optional[Engine] = session.get_bind()
        else:
            self._engine = None
        self._base = base
        self._tables = tables
        self._connection_strategy = connection_strategy

    @property
    def session(self) -> Union[Session, scoped_session]:
        if self._session is None:
            if self._engine is None:
                self.setup_connection()
            session_factory = sessionmaker(bind=self._engine)
            self._session = scoped_session(session_factory)
            self._was_session_created_here = True
        return self._session

    def setup_connection(self) -> None:
        assert isinstance(self.settings, SQLAlchemySettings), self.settings
        if self._engine is None:
            if self.is_sqlite():
                kwargs: Dict[str, Any] = {"connect_args": {"check_same_thread": False}}
            elif self.settings.pool_size == 1:
                kwargs = {"poolclass": StaticPool}
            else:
                kwargs = {"pool_size": self.settings.pool_size}
            self._engine = create_engine(
                self.settings.uri,
                strategy=self._connection_strategy,
                # echo=True,
                **kwargs
            )
            assert self._engine

    # Experiment with shared cache in sqlite :memory: database. The snag is
    # that when the database is locked by one thread and another attempts to
    # access, then the other thread immediately raises an exception because
    # the database is locked. There are no concurrent transactions, so access
    # would need to be controlled with a lock.
    #
    # def setup_connection(self):
    #     assert isinstance(self.settings, SQLAlchemySettings), self.settings
    #     if self._engine is None:
    #         args = []
    #         kwargs = {}
    #         if self.is_sqlite():
    #             kwargs['connect_args'] = {
    #                 'check_same_thread': False,
    #             }
    #
    #             if self.settings.uri == SQLITE_IN_MEMORY:
    #                 # Do some things to pass in cache=shared, so in-memory database
    #                 # has a shared (rather than private) cache, which makes it work
    #                 # with multiple threads.
    #                 PY2 = sys.version_info.major == 2
    #                 if PY2:
    #                     params = {}
    #                 else:
    #                     params = {'uri': True}
    #                     kwargs['creator'] = lambda: sqlite3.connect('file::memory:?cache=shared', **params)
    #                 args.append('sqlite://')
    #             else:
    #                 args.append(self.settings.uri)
    #
    #         elif self.settings.pool_size == 1:
    #             kwargs['poolclass'] = StaticPool
    #             args.append(self.settings.uri)
    #         else:
    #             kwargs['pool_size'] = self.settings.pool_size
    #             args.append(self.settings.uri)
    #
    #         self._engine = create_engine(
    #             strategy=self._connection_strategy,
    #             *args,
    #             **kwargs
    #         )
    #         assert self._engine

    def is_sqlite(self) -> bool:
        return self.settings.uri is not None and self.settings.uri.startswith("sqlite")

    def setup_tables(self) -> None:
        if self._tables is not None:
            for table in self._tables:
                self.setup_table(table)

    def setup_table(self, table: Any) -> None:
        if self._engine is None:
            raise Exception("Engine not set when required: {}".format(self))
        try:
            table.__table__.create(self._engine, checkfirst=True)
        except InternalError as e:
            if "Table '{}' already exists".format(table.__tablename__) in str(e):
                # This is a race condition from checkfirst=True. Can happen
                # if two threads call this method at the same time.
                pass
            else:
                raise

    def drop_tables(self) -> None:
        if self._tables is not None:
            for table in self._tables:
                self.drop_table(table)

    def drop_table(self, table: Any) -> None:
        table.__table__.drop(self._engine, checkfirst=True)

    def truncate_tables(self) -> None:
        self.drop_tables()

    def close_connection(self) -> None:
        if self._was_session_created_here:
            if self._session:
                self._session.close()
                self._session = None
            if self._engine:
                # Call dispose(), unless sqlite (to avoid error 'stored_events'
                # table does not exist in projections.rst doc).
                if not self.is_sqlite():
                    self._engine.dispose()
                self._engine = None
