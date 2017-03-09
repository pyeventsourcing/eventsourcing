from random import random
from time import sleep

import six
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlalchemy.sql.expression import asc, desc
from sqlalchemy.sql.schema import Column, Sequence, UniqueConstraint
from sqlalchemy.sql.sqltypes import BigInteger, Integer, String, Text

from eventsourcing.exceptions import ConcurrencyError, DatasourceOperationError
from eventsourcing.infrastructure.datastore.sqlalchemyorm import Base, SQLAlchemyDatastore
from eventsourcing.infrastructure.eventstore import AbstractStoredEventRepository
from eventsourcing.infrastructure.transcoding import EntityVersion
from eventsourcing.utils.time import timestamp_long_from_uuid


class SqlEntityVersion(Base):
    __tablename__ = 'entity_versions'

    entity_version_id = Column(String(355), primary_key=True)
    event_id = Column(String(255))


class SqlStoredEvent(Base):
    __tablename__ = 'storedevents'

    id = Column(Integer, Sequence('stored_event_id_seq'), primary_key=True)
    stored_entity_id = Column(String(255), index=True)
    event_id = Column(String(255), index=True)
    timestamp_long = Column(BigInteger(), index=True)
    event_topic = Column(String(255))
    event_attrs = Column(Text())

    # Unique contraint includes 'stored_entity_id' which is a good value
    # to partition on, because all events for an entity will be in the same
    # partition, which may help performance.
    __table_args__ = UniqueConstraint('stored_entity_id', 'event_id', name='stored_event_uc'),


class SQLAlchemyStoredEventRepository(AbstractStoredEventRepository):
    def __init__(self, datastore, stored_event_table, **kwargs):
        super(SQLAlchemyStoredEventRepository, self).__init__(**kwargs)
        self.stored_event_table = stored_event_table
        assert isinstance(datastore, SQLAlchemyDatastore), datastore
        self.datastore = datastore
        self._db_session = None

    @property
    def db_session(self):
        if self._db_session is None:
            assert isinstance(self.datastore, SQLAlchemyDatastore), self.datastore
            self._db_session = self.datastore.db_session
        return self._db_session

    def write_version_and_event(self, new_stored_event, new_version_number=None, max_retries=3,
                                artificial_failure_rate=0):
        """
        Writes new entity version and stored event into the database in a single transaction.
        """
        stored_entity_id = new_stored_event.stored_entity_id
        new_entity_version = None
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

                    # Commit the version number now to generate some contention.
                    #  - used to generate contention in tests
                    self.db_session.commit()
                    self.db_session.close()

                    # Increased latency here causes increased contention.
                    #  - used to generate contention in concurrency control tests
                    sleep(artificial_failure_rate)

                    # Optionally mimic an unreliable commit() operation.
                    #  - used for testing retries
                    if artificial_failure_rate and (random() > 1 - artificial_failure_rate):
                        raise DBAPIError("Artificial failure", (), '')

            # Write stored event into the transaction.
            self.db_session.add(self.to_sql(new_stored_event))

            # Commit the transaction.
            self.db_session.commit()

        except IntegrityError as e:
            # Rollback and raise concurrency error.
            self.db_session.rollback()
            raise ConcurrencyError("Version {} of entity {} already exists: {}"
                                   "".format(new_version_number, stored_entity_id, e))
        except DBAPIError as e:
            # Rollback and raise.
            self.db_session.rollback()
            try:
                if new_entity_version is not None:
                    self.db_session.delete(new_entity_version)
                    self.db_session.commit()
            finally:
                raise DatasourceOperationError(e)
        finally:
            # Begin new transaction.
            self.db_session.close()

    def get_entity_version(self, stored_entity_id, version_number):
        entity_version_id = self.make_entity_version_id(stored_entity_id, version_number)
        sql_entity_version = self.db_session.query(SqlEntityVersion).filter_by(
            entity_version_id=entity_version_id).first()
        if sql_entity_version is None:
            self.raise_entity_version_not_found(stored_entity_id, version_number)
        assert isinstance(sql_entity_version, SqlEntityVersion)
        return EntityVersion(
            entity_version_id=entity_version_id,
            event_id=sql_entity_version.event_id,
        )

    def get_stored_events(self, stored_entity_id, after=None, until=None, limit=None, query_ascending=True,
                          results_ascending=True, include_after_when_ascending=False,
                          include_until_when_descending=False):

        assert limit is None or limit >= 1, limit

        try:
            query = self.db_session.query(self.stored_event_table)
            query = query.filter_by(stored_entity_id=stored_entity_id)
            if query_ascending:
                query = query.order_by(asc(self.stored_event_table.timestamp_long))
            else:
                query = query.order_by(desc(self.stored_event_table.timestamp_long))

            if after is not None:
                if query_ascending and not include_after_when_ascending:
                    query = query.filter(self.stored_event_table.timestamp_long > timestamp_long_from_uuid(after))
                else:
                    query = query.filter(self.stored_event_table.timestamp_long >= timestamp_long_from_uuid(after))

            if until is not None:
                if query_ascending or include_until_when_descending:
                    query = query.filter(self.stored_event_table.timestamp_long <= timestamp_long_from_uuid(until))
                else:
                    query = query.filter(self.stored_event_table.timestamp_long < timestamp_long_from_uuid(until))

            if limit is not None:
                query = query.limit(limit)
            events = self.map(self.from_sql, query)
            events = list(events)
        finally:
            self.db_session.close()
        if results_ascending != query_ascending:
            events.reverse()
        return events

    def from_sql(self, sql_stored_event):
        assert isinstance(sql_stored_event, self.stored_event_table), sql_stored_event
        return self.stored_event_class(
            event_id=sql_stored_event.event_id,
            stored_entity_id=sql_stored_event.stored_entity_id,
            event_attrs=sql_stored_event.event_attrs,
            event_topic=sql_stored_event.event_topic
        )

    def to_sql(self, stored_event):
        assert isinstance(stored_event, self.stored_event_class)
        return self.stored_event_table(
            event_id=stored_event.event_id,
            timestamp_long=timestamp_long_from_uuid(stored_event.event_id),
            stored_entity_id=stored_event.stored_entity_id,
            event_attrs=stored_event.event_attrs,
            event_topic=stored_event.event_topic
        )
