import six
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql.expression import asc, desc
from sqlalchemy.sql.schema import Column, Index
from sqlalchemy.sql.sqltypes import BigInteger, Float, String, Text
from sqlalchemy_utils.types.uuid import UUIDType

from eventsourcing.infrastructure.activerecord import AbstractActiveRecordStrategy
from eventsourcing.infrastructure.sqlalchemy.datastore import ActiveRecord


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
            query = self.filter(**filter_args)
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
            filter_kwargs = {self.field_names.sequence_id: sequence_id}
            query = self.filter(**filter_kwargs)

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

    def filter(self, **kwargs):
        query = self.session.query(self.active_record_class)
        return query.filter_by(**kwargs)

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
        kwargs = self.get_field_kwargs(sequenced_item)
        return self.active_record_class(**kwargs)

    def all_items(self):
        """
        Returns all items across all sequences.
        """
        all_records = (r for r, _ in self.all_records())
        return map(self.from_active_record, all_records)

    def from_active_record(self, active_record):
        """
        Returns a sequenced item, from given active record.
        """
        kwargs = self.get_field_kwargs(active_record)
        return self.sequenced_item_class(**kwargs)

    def all_records(self, resume=None, *args, **kwargs):
        """
        Returns all records in the table.
        """
        query = self.filter(**kwargs)
        if resume is not None:
            query = query.offset(resume + 1)
        else:
            resume = 0
        query = query.limit(100)
        for i, record in enumerate(query):
            yield record, i + resume

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

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = Column(UUIDType(), primary_key=True)

    # Position (index) of item in sequence.
    position = Column(BigInteger(), primary_key=True)

    # Topic of the item (e.g. path to domain event class).
    topic = Column(String(255))

    # State of the item (serialized dict, possibly encrypted).
    data = Column(Text())

    __table_args__ = (
        Index('integer_sequenced_items_index', 'sequence_id', 'position'),
    )


class TimestampSequencedItemRecord(ActiveRecord):
    __tablename__ = 'timestamp_sequenced_items'

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = Column(UUIDType(), primary_key=True)

    # Position (timestamp) of item in sequence.
    position = Column(Float(), primary_key=True)

    # Topic of the item (e.g. path to domain event class).
    topic = Column(String(255))

    # State of the item (serialized dict, possibly encrypted).
    data = Column(Text())

    __table_args__ = (
        Index('timestamp_sequenced_items_index', 'sequence_id', 'position'),
    )


class SnapshotRecord(ActiveRecord):
    __tablename__ = 'snapshots'

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = Column(UUIDType(), primary_key=True)

    # Position (index) of item in sequence.
    position = Column(BigInteger(), primary_key=True)

    # Topic of the item (e.g. path to domain entity class).
    topic = Column(String(255))

    # State of the item (serialized dict, possibly encrypted).
    data = Column(Text())

    __table_args__ = (
        Index('snapshots_index', 'sequence_id', 'position'),
    )


class StoredEventRecord(ActiveRecord):
    __tablename__ = 'stored_events'

    # Originator ID (e.g. an entity or aggregate ID).
    originator_id = Column(UUIDType(), primary_key=True)

    # Originator version of item in sequence.
    originator_version = Column(BigInteger(), primary_key=True)

    # Type of the event (class name).
    event_type = Column(String(100))

    # State of the item (serialized dict, possibly encrypted).
    state = Column(Text())

    __table_args__ = Index('index', 'originator_id', 'originator_version'),
