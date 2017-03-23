import six
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql.expression import asc, desc
from sqlalchemy.sql.schema import Column, Sequence, UniqueConstraint
from sqlalchemy.sql.sqltypes import BigInteger, Float, Integer, String, Text
from sqlalchemy_utils.types.uuid import UUIDType

from eventsourcing.infrastructure.activerecord import AbstractActiveRecordStrategy
from eventsourcing.infrastructure.sqlalchemy.datastore import Base, SQLAlchemyDatastore


class SQLAlchemyActiveRecordStrategy(AbstractActiveRecordStrategy):

    def __init__(self, datastore, *args, **kwargs):
        assert isinstance(datastore, SQLAlchemyDatastore)
        super(SQLAlchemyActiveRecordStrategy, self).__init__(*args, **kwargs)
        self.datastore = datastore

    def append_item(self, item):
        active_record = self._to_active_record(item)
        try:
            # Write stored event into the transaction.
            self._add_record_to_session(active_record)

            # Commit the transaction.
            self.datastore.db_session.commit()

        except IntegrityError as e:
            # Roll back the transaction.
            self.datastore.db_session.rollback()
            self.raise_sequence_item_error(item.sequence_id, item.position, e)
        finally:
            # Begin new transaction.
            self.datastore.db_session.close()

    def get_item(self, sequence_id, eq):
        try:
            query = self._filter(sequence_id=sequence_id)
            query = query.filter(self.active_record_class.position == eq)
            events = six.moves.map(self._from_active_record, query)
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
            query = self._filter(sequence_id=sequence_id)

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

            events = six.moves.map(self._from_active_record, query)
            events = list(events)

        finally:
            self.datastore.db_session.close()

        if results_ascending != query_ascending:
            events.reverse()

        return events

    def _add_record_to_session(self, active_record):
        if isinstance(active_record, list):
            for r in active_record:
                self._add_record_to_session(r)
        else:
            self.datastore.db_session.add(active_record)

    def _to_active_record(self, sequenced_item):
        """
        Returns an active record, from given sequenced item.
        """
        if isinstance(sequenced_item, list):
            return [self._to_active_record(i) for i in sequenced_item]
        assert isinstance(sequenced_item, self.sequenced_item_class), type(sequenced_item)
        return self.active_record_class(
            sequence_id=sequenced_item.sequence_id,
            position=sequenced_item.position,
            topic=sequenced_item.topic,
            data=sequenced_item.data
        )

    def _from_active_record(self, active_record):
        """
        Returns a sequenced item, from given active record.
        """
        return self.sequenced_item_class(
            sequence_id=active_record.sequence_id,
            position=active_record.position,
            topic=active_record.topic,
            data=active_record.data,
        )

    def _filter(self, *args, **kwargs):
        query = self.datastore.db_session.query(self.active_record_class)
        return query.filter_by(*args, **kwargs)


class SqlIntegerSequencedItem(Base):
    __tablename__ = 'integer_sequenced_items'

    id = Column(Integer, Sequence('integer_sequened_item_id_seq'), primary_key=True)

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = Column(UUIDType(), index=True)

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
    sequence_id = Column(UUIDType(), index=True)

    # Position (timestamp) of item in sequence.
    position = Column(Float(), index=True)

    # Topic of the item (e.g. path to domain event class).
    topic = Column(String(255))

    # State of the item (serialized dict, possibly encrypted).
    data = Column(Text())
