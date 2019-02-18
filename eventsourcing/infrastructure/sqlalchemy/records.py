from sqlalchemy import DECIMAL, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql.schema import Column, Index
from sqlalchemy.sql.sqltypes import BigInteger, Integer, Text
from sqlalchemy_utils.types.uuid import UUIDType

Base = declarative_base()


# Please note, the record classes without an indexed ID ('WithID') are
# more or less equivalent to the similarly named Django classes. The
# record classes without ID ('NoID') are more or less equivalent to the
# Cassandra classes, in that they don't have a record ID, so must be
# accessed by sequence ID, optionally with position, and also their
# application sequence must be constructed elsewhere such as with a big
# array. Without record IDs, the maximum rate at which events can be
# written in parallel will be greater, because the IDs don't need to be
# generated and because there isn't a record ID index to be updated.
# Also, if there is no record ID index, the table can easily be shared
# with the sequence ID being used to select a shard. The drawback is
# that the application sequence will need to be constructed elsewhere.


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
    state = Column(Text())

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
    state = Column(Text())


IntegerSequencedRecord = IntegerSequencedWithIDRecord


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
    state = Column(Text())

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
    state = Column(Text())

    __table_args__ = (
        Index('timestamp_sequenced_items_noid_position_index', 'position', unique=False),
    )


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
    state = Column(Text())


class EntitySnapshotRecord(Base):
    __tablename__ = 'entity_snapshots'

    # Application ID.
    application_name = Column(String(length=32), primary_key=True)

    # Originator ID (e.g. an entity or aggregate ID).
    originator_id = Column(UUIDType(), primary_key=True)

    # Originator version of item in sequence.
    originator_version = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)

    # Topic of the item (e.g. path to domain entity class).
    topic = Column(Text(), nullable=False)

    # State of the item (serialized dict, possibly encrypted).
    state = Column(Text())


class StoredEventRecord(Base):
    __tablename__ = 'stored_events'

    # Application ID.
    application_name = Column(String(length=32), primary_key=True)

    # Originator ID (e.g. an entity or aggregate ID).
    originator_id = Column(UUIDType(), primary_key=True)

    # Originator version of item in sequence.
    originator_version = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)

    # Pipeline ID.
    pipeline_id = Column(Integer(), nullable=True)

    # Notification ID.
    notification_id = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=True)

    # Topic of the item (e.g. path to domain event class).
    topic = Column(Text(), nullable=False)

    # State of the item (serialized dict, possibly encrypted).
    state = Column(Text())

    # Causal dependencies.
    causal_dependencies = Column(Text())

    __table_args__ = (
        Index(
            'stored_events_notification_index',
            'application_name',
            'pipeline_id',
            'notification_id',
            unique=True,
        ),
    )


class NotificationTrackingRecord(Base):
    __tablename__ = 'notification_tracking'

    # Application name.
    application_name = Column(String(length=32), primary_key=True)

    # Upstream application name.
    upstream_application_name = Column(String(length=32), primary_key=True)

    # Pipeline ID.
    pipeline_id = Column(Integer(), primary_key=True)

    # Notification ID.
    notification_id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
