import six
from sqlalchemy import DECIMAL
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from sqlalchemy.sql.expression import asc, desc
from sqlalchemy.sql.schema import Column, Index
from sqlalchemy.sql.sqltypes import BigInteger, Integer, String, Text
from sqlalchemy_utils.types.uuid import UUIDType

from eventsourcing.exceptions import ProgrammingError
from eventsourcing.infrastructure.relationalactiverecordstrategy import RelationalActiveRecordStrategy
from eventsourcing.infrastructure.sqlalchemy.datastore import ActiveRecord


class SQLAlchemyActiveRecordStrategy(RelationalActiveRecordStrategy):
    def __init__(self, session, *args, **kwargs):
        super(SQLAlchemyActiveRecordStrategy, self).__init__(*args, **kwargs)
        self.session = session

    def _write_active_records(self, active_records, sequenced_items):
        try:
            # Add active record(s) to the transaction.
            for active_record in active_records:
                self.session.add(active_record)

            self.session.commit()
        except IntegrityError as e:
            self.session.rollback()
            self.raise_sequenced_item_error(sequenced_items)
        finally:
            self.session.close()

    def get_item(self, sequence_id, eq):
        try:
            filter_args = {self.field_names.sequence_id: sequence_id}
            query = self.filter(**filter_args)
            position_field = getattr(self.active_record_class, self.field_names.position)
            query = query.filter(position_field == eq)
            result = query.one()
        except (NoResultFound, MultipleResultsFound):
            raise IndexError
        finally:
            self.session.close()
        return self.from_active_record(result)

        # try:
        #     return events[0]
        # except IndexError:
        #     self.raise_index_error(eq)

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

            results = query.all()

        finally:
            self.session.close()

        if results_ascending != query_ascending:
            # This code path is under test, but not otherwise used ATM.
            results.reverse()

        for item in six.moves.map(self.from_active_record, results):
            yield item

    def filter(self, **kwargs):
        return self.query.filter_by(**kwargs)

    @property
    def query(self):
        return self.session.query(self.active_record_class)

    def all_items(self):
        """
        Returns all items across all sequences.
        """
        return six.moves.map(self.from_active_record, self.all_records())

    def from_active_record(self, active_record):
        """
        Returns a sequenced item, from given active record.
        """
        kwargs = self.get_field_kwargs(active_record)
        return self.sequenced_item_class(**kwargs)

    def all_records(self, *args, **kwargs):
        """
        Returns all records in the table.
        """
        # query = self.filter(**kwargs)
        # if resume is not None:
        #     query = query.offset(resume + 1)
        # else:
        #     resume = 0
        # query = query.limit(100)
        # for i, record in enumerate(query):
        #     yield record, i + resume
        try:
            return self.query.all()
        finally:
            self.session.close()

    def delete_record(self, record):
        """
        Permanently removes record from table.
        """
        try:
            self.session.delete(record)
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            raise ProgrammingError(e)
        finally:
            self.session.close()


class IntegerSequencedItemRecord(ActiveRecord):
    __tablename__ = 'integer_sequenced_items'

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = Column(UUIDType(), nullable=False)

    # Position (index) of item in sequence.
    position = Column(BigInteger(), nullable=False)

    # Topic of the item (e.g. path to domain event class).
    topic = Column(String(255), nullable=False)

    # State of the item (serialized dict, possibly encrypted).
    data = Column(Text())

    __table_args__ = (
        Index('integer_sequenced_items_index', 'sequence_id', 'position', unique=True),
    )


class TimestampSequencedItemRecord(ActiveRecord):
    __tablename__ = 'timestamp_sequenced_items'

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = Column(UUIDType(), nullable=False)

    # Position (timestamp) of item in sequence.
    position = Column(DECIMAL(24, 6, 6), nullable=False)
    # position = Column(DECIMAL(27, 9, 9), nullable=False)

    # Topic of the item (e.g. path to domain event class).
    topic = Column(String(255), nullable=False)

    # State of the item (serialized dict, possibly encrypted).
    data = Column(Text())

    __table_args__ = (
        Index('timestamp_sequenced_items_index', 'sequence_id', 'position', unique=True),
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
    data = Column(Text(), nullable=False)


class StoredEventRecord(ActiveRecord):
    __tablename__ = 'stored_events'

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)

    # Originator ID (e.g. an entity or aggregate ID).
    originator_id = Column(UUIDType(), nullable=False)

    # Originator version of item in sequence.
    originator_version = Column(BigInteger(), nullable=False)

    # Type of the event (class name).
    event_type = Column(String(100), nullable=False)

    # State of the item (serialized dict, possibly encrypted).
    state = Column(Text())

    __table_args__ = Index('stored_events_index', 'originator_id', 'originator_version', unique=True),
