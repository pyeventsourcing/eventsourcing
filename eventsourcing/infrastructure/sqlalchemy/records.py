from sqlalchemy import DECIMAL, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql.schema import Column, Index
from sqlalchemy.sql.sqltypes import BigInteger, Integer, Text
from sqlalchemy_utils.types.uuid import UUIDType

Base = declarative_base()


class IntegerSequencedWithIDRecord(Base):
    __tablename__ = 'integer_sequenced_items'

    # Record ID.
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True, unique=True)

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = Column(UUIDType(), nullable=False)

    # Position (index) of item in sequence.
    position = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)

    # Topic of the item (e.g. path to domain event class).
    topic = Column(Text(), nullable=False)

    # State of the item (serialized dict, possibly encrypted).
    data = Column(Text())

    __table_args__ = (
        Index('integer_sequenced_items_sequence_id_position_index', 'sequence_id', 'position', unique=True),
    )


class IntegerSequencedNoIDRecord(Base):
    __tablename__ = 'integer_sequenced_items_noid'

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = Column(UUIDType(), primary_key=True)

    # Position (index) of item in sequence.
    position = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)

    # Topic of the item (e.g. path to domain event class).
    topic = Column(Text(), nullable=False)

    # State of the item (serialized dict, possibly encrypted).
    data = Column(Text())

IntegerSequencedRecord = IntegerSequencedWithIDRecord
# IntegerSequencedRecord = IntegerSequencedNoIDRecord


class TimestampSequencedWithIDRecord(Base):
    __tablename__ = 'timestamp_sequenced_items'

    # Record ID.
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True, unique=True,
                autoincrement=True)

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = Column(UUIDType(), nullable=False)

    # Position (timestamp) of item in sequence.
    position = Column(DECIMAL(24, 6, 6), nullable=False, unique=False)

    # Topic of the item (e.g. path to domain event class).
    topic = Column(Text(), nullable=False)

    # State of the item (serialized dict, possibly encrypted).
    data = Column(Text())

    __table_args__ = (
        Index('timestamp_sequenced_items_sequence_id_position_index', 'sequence_id', 'position', unique=True),
        Index('timestamp_sequenced_items_position_index', 'position', unique=False),
    )


class TimestampSequencedNoIDRecord(Base):
    __tablename__ = 'timestamp_sequenced_items_noid'

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = Column(UUIDType(), primary_key=True)

    # Position (timestamp) of item in sequence.
    position = Column(DECIMAL(24, 6, 6), primary_key=True)

    # Topic of the item (e.g. path to domain event class).
    topic = Column(Text(), nullable=False)

    # State of the item (serialized dict, possibly encrypted).
    data = Column(Text())

    __table_args__ = (
        Index('timestamp_sequenced_items_noid_position_index', 'position', unique=False),
    )


# TimestampSequencedRecord = TimestampSequencedWithIDRecord
TimestampSequencedRecord = TimestampSequencedNoIDRecord

class SnapshotRecord(Base):
    __tablename__ = 'snapshots'

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = Column(UUIDType(), primary_key=True)

    # Position (index) of item in sequence.
    position = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)

    # Topic of the item (e.g. path to domain entity class).
    topic = Column(Text(), nullable=False)

    # State of the item (serialized dict, possibly encrypted).
    data = Column(Text())


class StoredEventRecord(Base):
    __tablename__ = 'stored_events'

    # Record ID.
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True, unique=True)

    # Originator ID (e.g. an entity or aggregate ID).
    originator_id = Column(UUIDType(), nullable=False)

    # Originator version of item in sequence.
    originator_version = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)

    # Type of the event (class name).
    event_type = Column(Text(), nullable=False)

    # State of the item (serialized dict, possibly encrypted).
    state = Column(Text())

    __table_args__ = (
        Index('stored_events_sequence_id_position_index', 'originator_id', 'originator_version', unique=True),
    )
