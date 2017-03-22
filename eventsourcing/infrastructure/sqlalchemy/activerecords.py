import six
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.sql.expression import asc, desc
from sqlalchemy.sql.schema import Column, Sequence, UniqueConstraint
from sqlalchemy.sql.sqltypes import BigInteger, Float, Integer, String, Text

from eventsourcing.exceptions import DatasourceOperationError
from eventsourcing.infrastructure.activerecord import AbstractActiveRecordStrategy
from eventsourcing.infrastructure.sqlalchemy.datastore import Base, SQLAlchemyDatastore
from eventsourcing.utils.time import timestamp_long_from_uuid


class SQLAlchemyActiveRecordStrategy(AbstractActiveRecordStrategy):

    def __init__(self, datastore, *args, **kwargs):
        assert isinstance(datastore, SQLAlchemyDatastore)
        super(SQLAlchemyActiveRecordStrategy, self).__init__(*args, **kwargs)
        self.datastore = datastore

    def get_item(self, sequence_id, eq):
        try:
            query = self.filter(sequence_id=sequence_id)
            query = query.filter(self.active_record_class.position == eq)
            events = six.moves.map(self.from_active_record, query)
            events = list(events)
        finally:
            self.datastore.db_session.close()

        try:
            return events[0]
        except IndexError:
            self.raise_index_error(eq)

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
