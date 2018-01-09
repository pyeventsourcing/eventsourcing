from sqlalchemy import DECIMAL
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql.schema import Column, Index
from sqlalchemy.sql.sqltypes import BigInteger, Integer, String, Text
from sqlalchemy_utils.types.uuid import UUIDType

Base = declarative_base()


class IntegerSequencedRecord(Base):
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


class TimestampSequencedRecord(Base):
    __tablename__ = 'timestamp_sequenced_items'

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = Column(UUIDType(), nullable=False)

    # Position (timestamp) of item in sequence.
    position = Column(DECIMAL(24, 6, 6), nullable=False)

    # Topic of the item (e.g. path to domain event class).
    topic = Column(String(255), nullable=False)

    # State of the item (serialized dict, possibly encrypted).
    data = Column(Text())

    __table_args__ = (
        Index('timestamp_sequenced_items_index', 'sequence_id', 'position', unique=True),
    )


class SnapshotRecord(Base):
    __tablename__ = 'snapshots'

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = Column(UUIDType(), primary_key=True)

    # Position (index) of item in sequence.
    position = Column(BigInteger(), primary_key=True)

    # Topic of the item (e.g. path to domain entity class).
    topic = Column(String(255))

    # State of the item (serialized dict, possibly encrypted).
    data = Column(Text(), nullable=False)


class StoredEventRecord(Base):
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
