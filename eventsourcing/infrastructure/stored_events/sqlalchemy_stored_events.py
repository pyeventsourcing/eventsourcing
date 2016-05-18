from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative.api import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm.scoping import ScopedSession
from sqlalchemy.sql.expression import asc, desc
from sqlalchemy.sql.schema import Column, Sequence
from sqlalchemy.sql.sqltypes import Integer, String

from eventsourcing.infrastructure.stored_events.base import StoredEventRepository
from eventsourcing.infrastructure.stored_events.transcoders import StoredEvent


def get_scoped_session_facade(uri):
    assert uri is not None
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
    timestamp_ms = Column(Integer(), index=True)
    stored_entity_id = Column(String(), index=True)
    event_topic = Column(String(), index=True)
    event_attrs = Column(String())

    # def __repr__(self):
    #     return "<SqlStoredEvent(id='%s', event_id='%s', entity_id='%s', event_topic='%s', event_attrs='%s')>" % (
    #         self.id, self.event_id, self.entity_id, self.event_topic, self.event_attrs)


def stored_from_sql(sql_stored_event):
    assert isinstance(sql_stored_event, SqlStoredEvent), sql_stored_event
    return StoredEvent(
        event_id=UUID(sql_stored_event.event_id),
        stored_entity_id=sql_stored_event.stored_entity_id,
        event_attrs=sql_stored_event.event_attrs,
        event_topic=sql_stored_event.event_topic
    )


def sql_from_stored(stored_event):
    assert isinstance(stored_event, StoredEvent)
    return SqlStoredEvent(
        event_id=stored_event.event_id.hex,
        timestamp_ms=stored_event.event_id.time,
        stored_entity_id=stored_event.stored_entity_id,
        event_attrs=stored_event.event_attrs,
        event_topic=stored_event.event_topic
    )


class SQLAlchemyStoredEventRepository(StoredEventRepository):

    def __init__(self, db_session, **kwargs):
        super(SQLAlchemyStoredEventRepository, self).__init__(**kwargs)
        assert isinstance(db_session, ScopedSession)
        self.db_session = db_session

    def append(self, stored_event):
        sql_stored_event = sql_from_stored(stored_event)
        try:
            self.db_session.add(sql_stored_event)
            self.db_session.commit()
        except:
            self.db_session.rollback()
            raise
        finally:
            self.db_session.close() # Begins a new transaction

    def __contains__(self, event_id):
        return bool(self.db_session.query(SqlStoredEvent).filter_by(event_id=event_id.hex).count())

    def __getitem__(self, event_id):
        sql_stored_event = self.db_session.query(SqlStoredEvent).filter_by(event_id=event_id.hex).first()
        return stored_from_sql(sql_stored_event)

    def get_entity_events(self, stored_entity_id, since=None, before=None, limit=None):
        query = self.db_session.query(SqlStoredEvent)
        query = query.filter_by(stored_entity_id=stored_entity_id)
        query = query.order_by(asc(SqlStoredEvent.id))
        if since is not None:
            query = query.filter(SqlStoredEvent.timestamp_ms > since.time)
        if before is not None:
            query = query.filter(SqlStoredEvent.timestamp_ms < before.time)
        if limit is not None:
            query = query.limit(limit)
        sql_stored_events = query
        return self.map(stored_from_sql, sql_stored_events)

    def get_most_recent_event(self, stored_entity_id):
        query = self.db_session.query(SqlStoredEvent)
        query = query.filter_by(stored_entity_id=stored_entity_id)
        query = query.order_by(desc(SqlStoredEvent.id))
        sql_stored_event = query.first()
        return stored_from_sql(sql_stored_event) if sql_stored_event else None

    def get_topic_events(self, event_topic):
        sql_stored_events = self.db_session.query(SqlStoredEvent).filter_by(event_topic=event_topic).order_by(SqlStoredEvent.event_id.desc())
        return self.map(stored_from_sql, sql_stored_events)
