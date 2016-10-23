from time import sleep

import six
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.declarative.api import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm.scoping import ScopedSession
from sqlalchemy.sql.expression import asc, desc
from sqlalchemy.sql.schema import Column, Sequence
from sqlalchemy.sql.sqltypes import Integer, String, BigInteger, Text

from eventsourcing.domain.services.eventstore import AbstractStoredEventRepository
from eventsourcing.domain.services.transcoding import StoredEvent, EntityVersion
from eventsourcing.exceptions import ConcurrencyError, EntityVersionDoesNotExist
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

    entity_version_id = Column(String(355), primary_key=True)
    event_id = Column(String(255))


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


class SQLAlchemyStoredEventRepository(AbstractStoredEventRepository):

    def __init__(self, db_session, **kwargs):
        super(SQLAlchemyStoredEventRepository, self).__init__(**kwargs)
        assert isinstance(db_session, ScopedSession)
        self.db_session = db_session

    def write_version_and_event(self, new_stored_event, new_version_number=None, max_retries=3, artificial_failure_rate=0):
        """
        Writes new entity version and stored event into the database in a single transaction.
        """
        stored_entity_id = new_stored_event.stored_entity_id
        try:
            # Write entity version into the transaction.
            if self.always_write_entity_version and new_version_number is not None:
                assert isinstance(new_version_number, six.integer_types)
                new_entity_version_id = self.make_entity_version_id(stored_entity_id, new_version_number)
                new_entity_version = SqlEntityVersion(
                    entity_version_id=new_entity_version_id,
                    event_id=new_stored_event.event_id,
                )

                self.db_session.add(new_entity_version)

                if artificial_failure_rate:

                    # Todo: Add some retries and raise some artificial exceptions?
                    # if artificial_failure_rate and (random() > 1 - artificial_failure_rate):
                    #     raise Exception("Artificial failure")

                    # Commit the version number now to generate some contention.
                    #  - used to generate contention in tests
                    self.db_session.commit()
                    self.db_session.close()

                    # Increased latency here causes increased contention.
                    #  - used to generate contention in tests
                    sleep(artificial_failure_rate)

            # Write stored event into the transaction.
            self.db_session.add(to_sql(new_stored_event))

            # Commit the transaction.
            self.db_session.commit()

        except IntegrityError as e:
            # Rollback and raise concurrency error.
            self.db_session.rollback()
            raise ConcurrencyError("Version {} of entity {} already exists: {}"
                                   "".format(new_entity_version, stored_entity_id, e))
        except:
            # Rollback and reraise.
            self.db_session.rollback()
            raise
        finally:
            # Begin new transaction.
            self.db_session.close()

    def get_entity_version(self, stored_entity_id, version_number):
        entity_version_id = self.make_entity_version_id(stored_entity_id, version_number)
        version_number = self.db_session.query(SqlEntityVersion).filter_by(entity_version_id=entity_version_id).first()
        if version_number is None:
            raise EntityVersionDoesNotExist()
        assert isinstance(version_number, SqlEntityVersion)
        return EntityVersion(
            entity_version_id=entity_version_id,
            event_id=version_number.event_id,
        )

    def get_entity_events(self, stored_entity_id, after=None, until=None, limit=None, query_ascending=True,
                          results_ascending=True):
        try:
            query = self.db_session.query(SqlStoredEvent)
            query = query.filter_by(stored_entity_id=stored_entity_id)
            if query_ascending:
                query = query.order_by(asc(SqlStoredEvent.timestamp_long))
            else:
                query = query.order_by(desc(SqlStoredEvent.timestamp_long))

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
