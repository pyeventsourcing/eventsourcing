from time import sleep

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.declarative.api import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm.scoping import ScopedSession
from sqlalchemy.sql.expression import asc, desc
from sqlalchemy.sql.schema import Column, Sequence
from sqlalchemy.sql.sqltypes import Integer, String, BigInteger, Text

from eventsourcing.exceptions import ConcurrencyError
from eventsourcing.infrastructure.stored_events.base import StoredEventRepository
from eventsourcing.infrastructure.stored_events.transcoders import StoredEvent
from eventsourcing.utils.time import timestamp_long_from_uuid


def get_scoped_session_facade(uri):
    if uri is None:
        raise ValueError
    engine = create_engine(uri, strategy='threadlocal')
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    scoped_session_facade = scoped_session(session_factory)
    return scoped_session_facade


Base = declarative_base()


class SqlEntityVersion(Base):

    __tablename__ = 'entity_versions'

    id = Column(String(355), primary_key=True)


class SqlStoredEvent(Base):

    __tablename__ = 'stored_events'

    id = Column(Integer, Sequence('stored_event_id_seq'), primary_key=True)
    event_id = Column(String(255), index=True)
    timestamp_long = Column(BigInteger(), index=True)
    stored_entity_id = Column(String(255), index=True)
    event_topic = Column(String(255))
    event_attrs = Column(Text())


def from_sql(sql_stored_event):
    assert isinstance(sql_stored_event, SqlStoredEvent), sql_stored_event
    return StoredEvent(
        event_id=sql_stored_event.event_id,
        stored_entity_id=sql_stored_event.stored_entity_id,
        event_attrs=sql_stored_event.event_attrs,
        event_topic=sql_stored_event.event_topic
    )


def to_sql(stored_event):
    assert isinstance(stored_event, StoredEvent)
    return SqlStoredEvent(
        event_id=stored_event.event_id,
        timestamp_long=timestamp_long_from_uuid(stored_event.event_id),
        stored_entity_id=stored_event.stored_entity_id,
        event_attrs=stored_event.event_attrs,
        event_topic=stored_event.event_topic
    )


class SQLAlchemyStoredEventRepository(StoredEventRepository):

    serialize_with_uuid1 = True

    def __init__(self, db_session, **kwargs):
        super(SQLAlchemyStoredEventRepository, self).__init__(**kwargs)
        assert isinstance(db_session, ScopedSession)
        self.db_session = db_session

    def append(self, stored_event, expected_version=None, new_version=None, max_retries=3, artificial_failure_rate=0):
        # Convert stored event named tuple to an SQLAlchemy object.
        sql_stored_event = to_sql(stored_event)

        stored_entity_id = sql_stored_event.stored_entity_id
        if expected_version:
            expected_entity_version_id = self.make_entity_version_id(stored_entity_id, expected_version)
            expected_entity_version = self.db_session.query(SqlEntityVersion).filter_by(id=expected_entity_version_id).first()
            if expected_entity_version is None:
                raise ConcurrencyError("Expected version '{}' of stored entity '{}' not found."
                                       "".format(expected_version, stored_entity_id))

        try:
            # Create a new entity version record.
            if new_version is not None:
                new_entity_version_id = self.make_entity_version_id(stored_entity_id, new_version)
                new_entity_version = SqlEntityVersion(id=new_entity_version_id)
                self.db_session.add(new_entity_version)

                if artificial_failure_rate:

                    # Todo: Add some retries and raise some artificial exceptions?
                    # if artificial_failure_rate and (random() > 1 - artificial_failure_rate):
                    #     raise Exception("Artificial failure")

                    # Commit the version number now to generate some contention.
                    #  - used to generate contention in tests
                    self.db_session.commit()
                    self.db_session.close()
                    sleep(artificial_failure_rate)

            # Create a new stored event record.
            self.db_session.add(sql_stored_event)

            # Commit the transaction.
            self.db_session.commit()

        except IntegrityError as e:
            # Rollback and raise concurrency error.
            self.db_session.rollback()
            raise ConcurrencyError("Version {} of entity {} already exists: {}"
                                   "".format(new_version, stored_entity_id, e))
        except:
            # Rollback and reraise.
            self.db_session.rollback()
            raise
        finally:
            # Begin new transaction.
            self.db_session.close()

    def get_entity_events(self, stored_entity_id, after=None, until=None, limit=None, query_ascending=True,
                          results_ascending=True):
        try:
            query = self.db_session.query(SqlStoredEvent)
            query = query.filter_by(stored_entity_id=stored_entity_id)
            if query_ascending:
                query = query.order_by(asc(SqlStoredEvent.id))
            else:
                query = query.order_by(desc(SqlStoredEvent.id))

            if after is not None:
                if query_ascending:
                    query = query.filter(SqlStoredEvent.timestamp_long > timestamp_long_from_uuid(after))
                else:
                    query = query.filter(SqlStoredEvent.timestamp_long >= timestamp_long_from_uuid(after))

            if until is not None:
                if query_ascending:
                    query = query.filter(SqlStoredEvent.timestamp_long <= timestamp_long_from_uuid(until))
                else:
                    query = query.filter(SqlStoredEvent.timestamp_long < timestamp_long_from_uuid(until))

            if limit is not None:
                query = query.limit(limit)
            events = self.map(from_sql, query)
            events = list(events)
        finally:
            self.db_session.close()
        if results_ascending != query_ascending:
            events.reverse()
        return events
