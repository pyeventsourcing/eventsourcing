from sqlalchemy import DECIMAL
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql.schema import Column, Index
from sqlalchemy.sql.sqltypes import BigInteger, Integer, Text
from sqlalchemy_utils.types.uuid import UUIDType

Base = declarative_base()


class IntegerSequencedRecord(Base):
    __tablename__ = 'integer_sequenced_items'

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = Column(UUIDType(), primary_key=True)

    # Position (index) of item in sequence.
    position = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)

    # Topic of the item (e.g. path to domain event class).
    topic = Column(Text(), nullable=False)

    # State of the item (serialized dict, possibly encrypted).
    data = Column(Text())

    # Record ID.
    id = Column(BigInteger().with_variant(Integer, "sqlite"), autoincrement=True)

    __table_args__ = (
        Index('record_id_index', 'id', unique=True),
    )


class TimestampSequencedRecord(Base):
    __tablename__ = 'timestamp_sequenced_items'

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = Column(UUIDType(), primary_key=True)

    # Position (timestamp) of item in sequence.
    position = Column(DECIMAL(24, 6, 6), primary_key=True)

    # Topic of the item (e.g. path to domain event class).
    topic = Column(Text(), nullable=False)

    # State of the item (serialized dict, possibly encrypted).
    data = Column(Text())

    __table_args__ = (
        Index('position_index', 'position', unique=False),
    )


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

    # Originator ID (e.g. an entity or aggregate ID).
    originator_id = Column(UUIDType(), primary_key=True)

    # Originator version of item in sequence.
    originator_version = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)

    # Type of the event (class name).
    event_type = Column(Text(), nullable=False)

    # State of the item (serialized dict, possibly encrypted).
    state = Column(Text())

    # Record ID.
    id = Column(BigInteger().with_variant(Integer, "sqlite"))

    __table_args__ = (
        Index('record_id_index', 'id', unique=True),
    )
