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

    # Sequence ID (e.g. an entity or aggregate ID).
    originator_id = models.UUIDField()

    # Position (index) of item in sequence.
    originator_version = models.BigIntegerField()

    # Topic of the item (e.g. path to domain event class).
    event_type = models.CharField(max_length=255)

    # State of the item (serialized dict, possibly encrypted).
    state = models.TextField()

    class Meta:
        unique_together = (("originator_id", "originator_version"),)
        db_table = 'stored_events'
