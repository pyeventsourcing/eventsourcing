from sqlalchemy import create_engine
from sqlalchemy.ext.declarative.api import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm.scoping import ScopedSession
from sqlalchemy.sql.expression import asc, desc
from sqlalchemy.sql.schema import Column, Sequence
from sqlalchemy.sql.sqltypes import Integer, String, BigInteger, Text

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

    stored_entity_id = Column(String(255), primary_key=True)
    entity_version = Column(Integer)


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

    def append(self, stored_event, expected_version=None, new_version=None):
        sql_stored_event = to_sql(stored_event)
        try:
            self.__append_event_and_update_version(sql_stored_event)
            self.db_session.commit()
        except:
            self.db_session.rollback()
            raise
        finally:
            self.db_session.close()  # Begins a new transaction

    def __append_event_and_update_version(self, sql_stored_event):

        # Try doing this by updating with a where clause that specifies
        # the number and counting the number of updates, if 0 then it
        # didn't work so catch the transaction error and raise a
        #   concurrency error.

        # # Optimistic concurrency control.
        # new_stored_version = None
        # if new_version is not None:
        #     stored_entity_id = stored_event.stored_entity_id
        #     if expected_version is not None:
        #         # Read the expected version exists, raise concurrency exception if not.
        #         assert isinstance(expected_version, six.integer_types)
        #         expected_version_changed_id = self.make_version_changed_id(expected_version, stored_entity_id)
        #         try:
        #             CqlEntityVersion.filter(r=expected_version_changed_id).get()
        #         except CqlEntityVersion.DoesNotExist:
        #             raise ConcurrencyError("Expected version '{}' of stored entity '{}' not found."
        #                                    "".format(expected_version, stored_entity_id))
        #     # Write the next version.
        #     #  - Uses "if not exists" feature of Cassandra, so
        #     #    this operation is assumed to succeed only once.
        #     #  - Raises concurrency exception if a "light weight
        #     #    transaction" exception is raised by Cassandra.
        #     new_stored_version_id = self.make_version_changed_id(new_version, stored_entity_id)
        #     new_stored_version = CqlEntityVersion(r=new_stored_version_id)
        #     try:
        #         new_stored_version.save()
        #     except LWTException as e:
        #         raise ConcurrencyError("Couldn't update version because version already exists: {}".format(e))
        #
        # # Write the stored event into the database.
        # try:
        #     cql_stored_event = to_cql(stored_event)
        #     cql_stored_event.save()
        # except Exception as event_write_error:
        #     # If we get here, we're in trouble because the version has been
        #     # written, but perhaps not the event, so the entity may be broken
        #     # because it might not be possible to get the entity with version
        #     # number high enough to pass the optimistic concurrency check
        #     # when storing subsequent events.
        #     sleep(0.1)
        #     try:
        #         CqlStoredEvent.filter(n=stored_event.stored_entity_id, v=stored_event.event_id).get()
        #     except CqlStoredEvent.DoesNotExist:
        #         # Try hard to recover the situation by removing the
        #         # new version, otherwise the entity will be stuck.
        #         if new_stored_version is not None:
        #             retries = 5
        #             while True:
        #                 try:
        #                     new_stored_version.delete()
        #                 except Exception as version_delete_error:
        #                     if retries == 0:
        #                         raise Exception("Unable to delete version after failing to write event: {}: {}"
        #                                         "".format(event_write_error, version_delete_error))
        #                     else:
        #                         retries -= 1
        #                         sleep(0.05 + 0.1 * random())
        #                 else:
        #                     break
        #         raise event_write_error
        #     else:
        #         # If the event actually exists, despite the exception, all is well.
        #         pass
        self.db_session.add(sql_stored_event)

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
