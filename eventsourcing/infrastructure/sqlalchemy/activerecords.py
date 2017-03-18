from random import random
from time import sleep

import six
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.sql.expression import asc, desc
from sqlalchemy.sql.schema import Column, Sequence, UniqueConstraint
from sqlalchemy.sql.sqltypes import BigInteger, Float, Integer, String, Text

from eventsourcing.exceptions import ConcurrencyError, DatasourceOperationError
from eventsourcing.infrastructure.activerecord import AbstractActiveRecordStrategy
from eventsourcing.infrastructure.eventstore import AbstractStoredEventRepository
from eventsourcing.infrastructure.sqlalchemy.datastore import Base, SQLAlchemyDatastore
from eventsourcing.infrastructure.transcoding import EntityVersion
from eventsourcing.utils.time import timestamp_long_from_uuid


class SQLAlchemyActiveRecordStrategy(AbstractActiveRecordStrategy):

    def __init__(self, datastore, *args, **kwargs):
        assert isinstance(datastore, SQLAlchemyDatastore)
        super(SQLAlchemyActiveRecordStrategy, self).__init__(*args, **kwargs)
        self.datastore = datastore

    def get_items(self, sequence_id, gt=None, gte=None, lt=None, lte=None, limit=None,
                  query_ascending=True, results_ascending=True):

        assert limit is None or limit >= 1, limit

        try:
            query = self.filter(sequence_id=sequence_id)

            if query_ascending:
                query = query.order_by(asc(self.active_record_class.position))
            else:
                query = query.order_by(desc(self.active_record_class.position))

            if gt is not None:
                query = query.filter(self.active_record_class.position > gt)
            if gte is not None:
                query = query.filter(self.active_record_class.position >= gte)
            if lt is not None:
                query = query.filter(self.active_record_class.position < lt)
            if lte is not None:
                query = query.filter(self.active_record_class.position <= lte)

            if limit is not None:
                query = query.limit(limit)

            events = six.moves.map(self.from_active_record, query)
            events = list(events)

        finally:
            self.datastore.db_session.close()

        if results_ascending != query_ascending:
            events.reverse()

        return events

    def append_item(self, item):
        active_record = self.to_active_record(item)
        try:
            # Write stored event into the transaction.
            self.datastore.db_session.add(active_record)

            # Commit the transaction.
            self.datastore.db_session.commit()

        except IntegrityError as e:
            # Roll back the transaction.
            self.datastore.db_session.rollback()
            self.raise_sequence_item_error(item.sequence_id, item.position, e)
        except DBAPIError as e:
            self.raise_db_operation_error(e)
        finally:
            # Begin new transaction.
            self.datastore.db_session.close()

    def raise_db_operation_error(self, e):
        raise DatasourceOperationError(e)

    def to_active_record(self, sequenced_item):
        """
        Returns an active record, from given sequenced item.
        """
        assert isinstance(sequenced_item, self.sequenced_item_class), sequenced_item
        return self.active_record_class(
            sequence_id=sequenced_item.sequence_id,
            position=sequenced_item.position,
            topic=sequenced_item.topic,
            data=sequenced_item.data
        )

    def from_active_record(self, active_record):
        """
        Returns a sequenced item, from given active record.
        """
        return self.sequenced_item_class(
            sequence_id=active_record.sequence_id,
            position=active_record.position,
            topic=active_record.topic,
            data=active_record.data,
        )

    def filter(self, *args, **kwargs):
        query = self.datastore.db_session.query(self.active_record_class)
        return query.filter_by(*args, **kwargs)

    def from_sql(self, sql_stored_event):
        assert isinstance(sql_stored_event, self.stored_event_table), sql_stored_event
        return self.stored_event_class(
            event_id=sql_stored_event.event_id,
            stored_entity_id=sql_stored_event.entity_id,
            event_attrs=sql_stored_event.event_attrs,
            event_topic=sql_stored_event.event_topic
        )

    def to_sql(self, stored_event):
        assert isinstance(stored_event, self.stored_event_class)
        return self.stored_event_table(
            event_id=stored_event.event_id,
            timestamp_long=timestamp_long_from_uuid(stored_event.event_id),
            stored_entity_id=stored_event.entity_id,
            event_attrs=stored_event.event_attrs,
            event_topic=stored_event.event_topic
        )


class SqlEntityVersion(Base):
    __tablename__ = 'entity_versions'

    entity_version_id = Column(String(355), primary_key=True)
    event_id = Column(String(255))


class SqlIntegerSequencedItem(Base):
    __tablename__ = 'integer_sequenced_items'

    id = Column(Integer, Sequence('integer_sequened_item_id_seq'), primary_key=True)

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = Column(String(255), index=True)

    # Position (index) of item in sequence.
    position = Column(BigInteger(), index=True)

    # Topic of the item (e.g. path to domain event class).
    topic = Column(String(255))

    # State of the item (serialized dict, possibly encrypted).
    data = Column(Text())

    # Unique constraint includes 'entity_id' which is a good value
    # to partition on, because all events for an entity will be in the same
    # partition, which may help performance.
    __table_args__ = UniqueConstraint('sequence_id', 'position',
                                      name='integer_sequenced_item_uc'),


class SqlTimestampSequencedItem(Base):

    # Explicit table name.
    __tablename__ = 'timestamp_sequenced_items'

    # Unique constraint.
    __table_args__ = UniqueConstraint('sequence_id', 'position', name='time_sequenced_items_uc'),

    # Primary key.
    id = Column(Integer, Sequence('integer_sequened_item_id_seq'), primary_key=True)

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = Column(String(255), index=True)

    # Position (timestamp) of item in sequence.
    position = Column(Float(), index=True)

    # Topic of the item (e.g. path to domain event class).
    topic = Column(String(255))

    # State of the item (serialized dict, possibly encrypted).
    data = Column(Text())


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
        stored_entity_id = new_stored_event.entity_id
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
            stored_entity_id=sql_stored_event.entity_id,
            event_attrs=sql_stored_event.event_attrs,
            event_topic=sql_stored_event.event_topic
        )

    def to_sql(self, stored_event):
        assert isinstance(stored_event, self.stored_event_class)
        return self.stored_event_table(
            event_id=stored_event.event_id,
            timestamp_long=timestamp_long_from_uuid(stored_event.event_id),
            stored_entity_id=stored_event.entity_id,
            event_attrs=stored_event.event_attrs,
            event_topic=stored_event.event_topic
        )
