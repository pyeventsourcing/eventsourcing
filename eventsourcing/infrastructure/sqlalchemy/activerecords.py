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

    def append_item(self, sequenced_item):
        active_record = self.to_active_record(sequenced_item)
        try:
            # Write stored event into the transaction.
            self.add_record_to_session(active_record)

            # Commit the transaction.
            self.datastore.db_session.commit()

        except IntegrityError as e:
            # Roll back the transaction.
            self.datastore.db_session.rollback()
            self.raise_sequenced_item_error(sequenced_item, e)
        finally:
            # Begin new transaction.
            self.datastore.db_session.close()

    def get_item(self, sequence_id, eq):
        try:
            filter_args = {self.field_names.sequence_id: sequence_id}
            query = self.all_records(**filter_args)
            position_field = getattr(self.active_record_class, self.field_names.position)
            query = query.filter(position_field == eq)
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
            filter_args = {self.field_names.sequence_id: sequence_id}
            query = self.all_records(**filter_args)

            position_field = getattr(self.active_record_class, self.field_names.position)

            if query_ascending:
                query = query.order_by(asc(position_field))
            else:
                query = query.order_by(desc(position_field))

            if gt is not None:
                query = query.filter(position_field > gt)
            if gte is not None:
                query = query.filter(position_field >= gte)
            if lt is not None:
                query = query.filter(position_field < lt)
            if lte is not None:
                query = query.filter(position_field <= lte)

            if limit is not None:
                query = query.limit(limit)

            events = six.moves.map(self.from_active_record, query)
            events = list(events)

        finally:
            self.datastore.db_session.close()

        if results_ascending != query_ascending:
            events.reverse()

        return events

    def all_items(self):
        return map(self.from_active_record, self.all_records())

    def add_record_to_session(self, active_record):
        if isinstance(active_record, list):
            [self.add_record_to_session(r) for r in active_record]
        else:
            self.datastore.db_session.add(active_record)

    def to_active_record(self, sequenced_item):
        """
        Returns an active record, from given sequenced item.
        """
        # Recurse if it's a list.
        if isinstance(sequenced_item, list):
            return [self.to_active_record(i) for i in sequenced_item]

        # Check we got a sequenced item.
        assert isinstance(sequenced_item, self.sequenced_item_class), (self.sequenced_item_class, type(sequenced_item))

        # Construct and return an ORM object.
        orm_kwargs = {f: sequenced_item[i] for i, f in enumerate(self.field_names)}
        return self.active_record_class(**orm_kwargs)

    def from_active_record(self, active_record):
        """
        Returns a sequenced item, from given active record.
        """
        item_args = [getattr(active_record, f) for f in self.field_names]
        return self.sequenced_item_class(*item_args)

    def all_records(self, *args, **kwargs):
        query = self.datastore.db_session.query(self.active_record_class)
        return query.filter_by(*args, **kwargs)

    def delete_record(self, record):
        try:
            self.datastore.db_session.delete(record)
            self.datastore.db_session.commit()
        finally:
            # Begin new transaction.
            self.datastore.db_session.close()


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
    __table_args__ = UniqueConstraint('sequence_id', 'position', name='timestamp_sequenced_items_uc'),

    # Primary key.
    id = Column(Integer, Sequence('timestamp_sequened_item_id_seq'), primary_key=True)

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = Column(UUIDType(), index=True)

    # Position (timestamp) of item in sequence.
    position = Column(Float(), index=True)

    # Topic of the item (e.g. path to domain event class).
    topic = Column(String(255))

    # State of the item (serialized dict, possibly encrypted).
    data = Column(Text())


class SqlSnapshot(Base):
    __tablename__ = 'snapshots'

    id = Column(Integer, Sequence('snapshot_seq'), primary_key=True)

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = Column(UUIDType(), index=True)

    # Position (index) of item in sequence.
    position = Column(BigInteger(), index=True)

    # Topic of the item (e.g. path to domain entity class).
    topic = Column(String(255))

    # State of the item (serialized dict, possibly encrypted).
    data = Column(Text())

    # Unique constraint includes 'sequence_id' which is a good value
    # to partition on, because all events for an entity will be in the same
    # partition, which may help performance.
    __table_args__ = UniqueConstraint('sequence_id', 'position',
                                      name='snapshot_uc'),
