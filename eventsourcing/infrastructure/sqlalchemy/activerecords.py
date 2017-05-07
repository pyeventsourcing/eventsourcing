import six
from coverage.data import os
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.indexable import index_property
from sqlalchemy.sql.expression import asc, desc
from sqlalchemy.sql.schema import Column, Sequence, UniqueConstraint
from sqlalchemy.sql.sqltypes import BigInteger, Float, Integer, String, Text
from sqlalchemy_utils.types.uuid import UUIDType

from eventsourcing.infrastructure.activerecord import AbstractActiveRecordStrategy
from eventsourcing.infrastructure.sqlalchemy.datastore import ActiveRecord

with_new_index = bool(os.environ.get("WITH_NEW_INDEX"))
with_old_index = bool(os.environ.get("WITH_OLD_INDEX"))


class SQLAlchemyActiveRecordStrategy(AbstractActiveRecordStrategy):
    def __init__(self, session, *args, **kwargs):
        super(SQLAlchemyActiveRecordStrategy, self).__init__(*args, **kwargs)
        self.session = session

    def append(self, sequenced_item_or_items):
        # Convert sequenced item(s) to active_record(s).
        if isinstance(sequenced_item_or_items, list):
            active_records = [self.to_active_record(i) for i in sequenced_item_or_items]
        else:
            active_records = [self.to_active_record(sequenced_item_or_items)]
        try:
            # Add active record(s) to the transaction.
            for active_record in active_records:
                self.add_record_to_session(active_record)

            # Commit the transaction.
            self.session.commit()

        except IntegrityError as e:
            # Roll back the transaction.
            self.session.rollback()
            self.raise_sequenced_item_error(sequenced_item_or_items, e)
        finally:
            # Begin new transaction.
            self.session.close()

    def get_item(self, sequence_id, eq):
        try:
            filter_args = {self.field_names.sequence_id: sequence_id}
            query = self.all_records(**filter_args)
            position_field = getattr(self.active_record_class, self.field_names.position)
            query = query.filter(position_field == eq)
            events = six.moves.map(self.from_active_record, query)
            events = list(events)
        finally:
            self.session.close()

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
            self.session.close()

        if results_ascending != query_ascending:
            events.reverse()

        return events

    def add_record_to_session(self, active_record):
        """
        Adds active record to session.
        """
        self.session.add(active_record)

    def to_active_record(self, sequenced_item):
        """
        Returns an active record, from given sequenced item.
        """
        # Check we got a sequenced item.
        assert isinstance(sequenced_item, self.sequenced_item_class), (self.sequenced_item_class, type(sequenced_item))

        # Construct and return an ORM object.
        orm_kwargs = {f: sequenced_item[i] for i, f in enumerate(self.field_names)}
        return self.active_record_class(**orm_kwargs)

    def all_items(self):
        """
        Returns all items across all sequences.
        """
        return map(self.from_active_record, self.all_records())

    def from_active_record(self, active_record):
        """
        Returns a sequenced item, from given active record.
        """
        item_args = [getattr(active_record, f) for f in self.field_names]
        return self.sequenced_item_class(*item_args)

    def all_records(self, *args, **kwargs):
        """
        Returns all records in the table.
        """
        query = self.session.query(self.active_record_class)
        return query.filter_by(*args, **kwargs)

    def delete_record(self, record):
        """
        Permanently removes record from table.
        """
        try:
            self.session.delete(record)
            self.session.commit()
        finally:
            # Begin new transaction.
            self.session.close()


class IntegerSequencedItemRecord(ActiveRecord):
    __tablename__ = 'integer_sequenced_items'

    id = Column(Integer, Sequence('integer_sequenced_item_id_seq'), primary_key=True)

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = Column(UUIDType(), index=with_old_index)

    # Position (index) of item in sequence.
    position = Column(BigInteger(), index=with_old_index)

    # Topic of the item (e.g. path to domain event class).
    topic = Column(String(255))

    # State of the item (serialized dict, possibly encrypted).
    data = Column(Text())

    # Unique constraint includes 'sequence_id' and 'position'.
    __table_args__ = UniqueConstraint('sequence_id', 'position',
                                      name='integer_sequenced_item_uc'),

    if with_new_index:
        index = index_property('sequence_id', '-position')


class TimestampSequencedItemRecord(ActiveRecord):
    # Explicit table name.
    __tablename__ = 'timestamp_sequenced_items'

    # Unique constraint.
    __table_args__ = UniqueConstraint('sequence_id', 'position', name='timestamp_sequenced_items_uc'),

    # Primary key.
    id = Column(Integer, Sequence('timestamp_sequenced_item_id_seq'), primary_key=True)

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = Column(UUIDType(), index=with_old_index)

    # Position (timestamp) of item in sequence.
    position = Column(Float(), index=with_old_index)

    # Topic of the item (e.g. path to domain event class).
    topic = Column(String(255))

    # State of the item (serialized dict, possibly encrypted).
    data = Column(Text())

    if with_new_index:
        index = index_property('sequence_id', '-position')


# timestamp_sequence_index = Index("some_index", TimestampSequencedItemRecord.sequence_id,
#                                  TimestampSequencedItemRecord.position)
# #                                  # TimestampSequencedItemRecord.position.descending())
# #
# TimestampSequencedItemRecord.meta.append_constraint(timestamp_sequence_index)


class SnapshotRecord(ActiveRecord):
    __tablename__ = 'snapshots'

    id = Column(Integer, Sequence('snapshot_seq'), primary_key=True)

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = Column(UUIDType(), index=with_old_index)

    # Position (index) of item in sequence.
    position = Column(BigInteger(), index=with_old_index)

    # Topic of the item (e.g. path to domain entity class).
    topic = Column(String(255))

    # State of the item (serialized dict, possibly encrypted).
    data = Column(Text())

    # Unique constraint includes 'sequence_id' and 'position'.
    __table_args__ = UniqueConstraint('sequence_id', 'position',
                                      name='snapshot_uc'),

    if with_new_index:
        index = index_property('sequence_id', '-position')
