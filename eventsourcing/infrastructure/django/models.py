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

    def __init__(self, *args, **kwargs):
        super(TimestampSequencedItemRecord, self).__init__(*args, **kwargs)

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = models.UUIDField()

    # Position (timestamp) of item in sequence.
    position = models.DecimalField(max_digits=24, decimal_places=6)

    # Topic of the item (e.g. path to domain event class).
    topic = models.CharField(max_length=255)

    # State of the item (serialized dict, possibly encrypted).
    data = models.TextField()

    class Meta:
        unique_together = (("sequence_id", "position"),)
        db_table = 'timestamp_sequenced_items'


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
