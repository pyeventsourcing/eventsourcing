from django.db import models


class IntegerSequencedRecord(models.Model):

    id = models.BigAutoField(primary_key=True)

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = models.UUIDField()

    # Position (index) of item in sequence.
    position = models.BigIntegerField()

    # Topic of the item (e.g. path to domain event class).
    topic = models.TextField()

    # State of the item (serialized dict, possibly encrypted).
    state = models.TextField()

    class Meta:
        unique_together = (("sequence_id", "position"),)
        db_table = 'integer_sequenced_items'


class TimestampSequencedRecord(models.Model):

    id = models.BigAutoField(primary_key=True)

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = models.UUIDField()

    # Position (timestamp) of item in sequence.
    position = models.DecimalField(max_digits=24, decimal_places=6)

    # Topic of the item (e.g. path to domain event class).
    topic = models.TextField()

    # State of the item (serialized dict, possibly encrypted).
    state = models.TextField()

    class Meta:
        unique_together = (("sequence_id", "position"),)
        db_table = 'timestamp_sequenced_items'
        indexes = [
            models.Index(fields=['position'], name='position_idx'),
        ]


class SnapshotRecord(models.Model):

    uid = models.BigAutoField(primary_key=True)

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = models.UUIDField()

    # Position (index) of item in sequence.
    position = models.BigIntegerField()

    # Topic of the item (e.g. path to domain event class).
    topic = models.TextField()

    # State of the item (serialized dict, possibly encrypted).
    state = models.TextField()

    class Meta:
        unique_together = (("sequence_id", "position"),)
        db_table = 'snapshots'


class EntitySnapshotRecord(models.Model):

    uid = models.BigAutoField(primary_key=True)

    # Application name.
    application_name = models.CharField(max_length=32)

    # Originator ID (e.g. an entity or aggregate ID).
    originator_id = models.UUIDField()

    # Originator version of item in sequence.
    originator_version = models.BigIntegerField()

    # Topic of the item (e.g. path to domain event class).
    topic = models.TextField()

    # State of the item (serialized dict, possibly encrypted).
    state = models.TextField()

    class Meta:
        unique_together = (
            ("application_name", "originator_id", "originator_version"),
        )
        db_table = 'entity_snapshots'


class StoredEventRecord(models.Model):

    uid = models.BigAutoField(primary_key=True)

    # Application name.
    application_name = models.CharField(max_length=32)

    # Sequence ID (e.g. an entity or aggregate ID).
    originator_id = models.UUIDField()

    # Position (index) of item in sequence.
    originator_version = models.BigIntegerField()

    # Upstream application name.
    pipeline_id = models.IntegerField()

    # Notification ID.
    notification_id = models.BigIntegerField()

    # Topic of the item (e.g. path to domain event class).
    topic = models.TextField()

    # State of the item (serialized dict, possibly encrypted).
    state = models.TextField()

    # Causal dependencies.
    causal_dependencies = models.TextField()

    class Meta:
        unique_together = (
            ("application_name", "originator_id", "originator_version"),
            ("application_name", "pipeline_id", "notification_id"),
        )
        db_table = 'stored_events'


class NotificationTrackingRecord(models.Model):

    uid = models.BigAutoField(primary_key=True)

    # Application name.
    application_name = models.CharField(max_length=32)

    # Upstream application name.
    upstream_application_name = models.CharField(max_length=32)

    # Pipeline ID.
    pipeline_id = models.IntegerField()

    # Notification ID.
    notification_id = models.BigIntegerField()

    class Meta:
        unique_together = (
            (
                "application_name",
                "upstream_application_name",
                "pipeline_id",
                "notification_id"
            ),
        )
        db_table = 'notification_tracking'
