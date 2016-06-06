from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative.api import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm.scoping import ScopedSession
from sqlalchemy.sql.expression import asc, desc
from sqlalchemy.sql.schema import Column, Sequence
from sqlalchemy.sql.sqltypes import Integer, String, BigInteger

from eventsourcing.infrastructure.stored_events.base import StoredEventRepository
from eventsourcing.infrastructure.stored_events.transcoders import StoredEvent
from eventsourcing.utils.time import timestamp_long_from_uuid


def get_scoped_session_facade(uri):
    if uri is None: raise ValueError
    engine = create_engine(uri)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    scoped_session_facade = scoped_session(session_factory)
    return scoped_session_facade


Base = declarative_base()


class SqlStoredEvent(Base):

    __tablename__ = 'stored_events'

    id = Column(Integer, Sequence('stored_event_id_seq'), primary_key=True)
    event_id = Column(String(), index=True)
    timestamp_long = Column(BigInteger(), index=True)
    stored_entity_id = Column(String(), index=True)
    event_topic = Column(String())
    event_attrs = Column(String())

    # def __repr__(self):
    #     return "<SqlStoredEvent(id='%s', event_id='%s', entity_id='%s', event_topic='%s', event_attrs='%s')>" % (
    #         self.id, self.event_id, self.entity_id, self.event_topic, self.event_attrs)


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

    def append(self, stored_event):
        sql_stored_event = to_sql(stored_event)
        try:
            self.db_session.add(sql_stored_event)
            self.db_session.commit()
        except:
            self.db_session.rollback()
            raise
        finally:
            self.db_session.close() # Begins a new transaction

    # def __contains__(self, pk):
    #     (stored_entity_id, event_id) = pk
    #     query = self.db_session.query(SqlStoredEvent)
    #     query = query.filter_by(stored_entity_id=stored_entity_id, event_id=event_id.hex)
    #     return bool(query.count())
    #
    # def __getitem__(self, pk):
    #     (stored_entity_id, event_id) = pk
    #     query = self.db_session.query(SqlStoredEvent)
    #     query = query.filter_by(stored_entity_id=stored_entity_id, event_id=event_id.hex)
    #     sql_stored_event = query.first()
    #     if sql_stored_event is not None:
    #         return from_sql(sql_stored_event)
    #     else:
    #         raise KeyError
    #
    def get_entity_events(self, stored_entity_id, after=None, until=None, limit=None, query_asc=False):
        query = self.db_session.query(SqlStoredEvent)
        query = query.filter_by(stored_entity_id=stored_entity_id)
        if query_asc:
            query = query.order_by(asc(SqlStoredEvent.id))
        else:
            query = query.order_by(desc(SqlStoredEvent.id))
        if until is not None:
            query = query.filter(SqlStoredEvent.timestamp_long <= timestamp_long_from_uuid(until))
        if after is not None:
            query = query.filter(SqlStoredEvent.timestamp_long > timestamp_long_from_uuid(after))
        if limit is not None:
            query = query.limit(limit)
        events = self.map(from_sql, query)
        if not query_asc:
            events = reversed(list(events))
        return events

    def get_most_recent_event(self, stored_entity_id, until=None):
        query = self.db_session.query(SqlStoredEvent)
        query = query.filter_by(stored_entity_id=stored_entity_id)
        query = query.order_by(desc(SqlStoredEvent.id))
        if until is not None:
            query = query.filter(SqlStoredEvent.timestamp_long <= timestamp_long_from_uuid(until))
        sql_stored_event = query.first()
        return from_sql(sql_stored_event) if sql_stored_event else None
