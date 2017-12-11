from django.db import models


class IntegerSequencedItemRecord(models.Model):

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = models.UUIDField()

    # Position (index) of item in sequence.
    position = models.BigIntegerField()

    # Topic of the item (e.g. path to domain event class).
    topic = models.CharField(max_length=255)

    # State of the item (serialized dict, possibly encrypted).
    data = models.TextField()

    class Meta:
        unique_together = (("sequence_id", "position"),)
        db_table = 'integer_sequenced_items'



class TimestampSequencedItemRecord(models.Model):
    pass
    # id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    #
    # # Sequence ID (e.g. an entity or aggregate ID).
    # sequence_id = Column(UUIDType(), nullable=False)
    #
    # # Position (timestamp) of item in sequence.
    # position = Column(DECIMAL(24, 6, 6), nullable=False)
    # # position = Column(DECIMAL(27, 9, 9), nullable=False)
    #
    # # Topic of the item (e.g. path to domain event class).
    # topic = Column(String(255), nullable=False)
    #
    # # State of the item (serialized dict, possibly encrypted).
    # data = Column(Text())
    #
    # __table_args__ = (
    #     Index('timestamp_sequenced_items_index', 'sequence_id', 'position', unique=True),
    # )


class SnapshotRecord(models.Model):

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = models.UUIDField()

    # Position (index) of item in sequence.
    position = models.BigIntegerField()

    # Topic of the item (e.g. path to domain event class).
    topic = models.CharField(max_length=255)

    # State of the item (serialized dict, possibly encrypted).
    data = models.TextField()

    class Meta:
        unique_together = (("sequence_id", "position"),)
        db_table = 'snapshots'

class StoredEventRecord(models.Model):
    __tablename__ = 'stored_events'

    # id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    #
    # # Originator ID (e.g. an entity or aggregate ID).
    # originator_id = Column(UUIDType(), nullable=False)
    #
    # # Originator version of item in sequence.
    # originator_version = Column(BigInteger(), nullable=False)
    #
    # # Type of the event (class name).
    # event_type = Column(String(100), nullable=False)
    #
    # # State of the item (serialized dict, possibly encrypted).
    # state = Column(Text())
    #
    # __table_args__ = Index('stored_events_index', 'originator_id', 'originator_version', unique=True),
