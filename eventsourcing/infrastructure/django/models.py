from django.db import models
from django.utils.translation import gettext_lazy as _

__all__ = (
    "AbstractEntitySnapshotRecord",
    "AbstractIntegerSequencedRecord",
    "AbstractNotificationTrackingRecord",
    "AbstractSnapshotRecord",
    "AbstractStoredEventRecord",
    "AbstractTimestampSequencedRecord",
    "ABSTRACT_MODELS",
)


class AbstractIntegerSequencedRecord(models.Model):
    id = models.BigAutoField(primary_key=True)

    sequence_id = models.UUIDField(
        help_text=_("Sequence ID (e.g. an entity or aggregate ID)."),
    )
    position = models.BigIntegerField(
        help_text=_("Position (index) of item in sequence."),
    )
    topic = models.TextField(
        help_text=_("Topic of the item (e.g. path to domain event class).")
    )
    state = models.BinaryField(
        help_text=_("State of the item (serialized dict, possibly encrypted).")
    )

    class Meta:
        abstract = True
        unique_together = (("sequence_id", "position"),)


class AbstractTimestampSequencedRecord(models.Model):
    id = models.BigAutoField(primary_key=True)

    sequence_id = models.UUIDField(
        help_text=_("Sequence ID (e.g. an entity or aggregate ID).")
    )
    position = models.DecimalField(
        db_index=True,
        max_digits=24,
        decimal_places=6,
        help_text=_("Position (timestamp) of item in sequence."),
    )
    topic = models.TextField(
        help_text=_("Topic of the item (e.g. path to domain event class).")
    )
    state = models.BinaryField(
        help_text=_("State of the item (serialized dict, possibly encrypted).")
    )

    class Meta:
        abstract = True
        unique_together = (("sequence_id", "position"),)


class AbstractSnapshotRecord(models.Model):
    uid = models.BigAutoField(primary_key=True)

    sequence_id = models.UUIDField(
        help_text=_("Sequence ID (e.g. an entity or aggregate ID).")
    )
    position = models.BigIntegerField(
        help_text=_("Position (index) of item in sequence.")
    )
    topic = models.TextField(
        help_text=_("Topic of the item (e.g. path to domain event class).")
    )
    state = models.BinaryField(
        help_text=_("State of the item (serialized dict, possibly encrypted).")
    )

    class Meta:
        abstract = True
        unique_together = (("sequence_id", "position"),)


class AbstractEntitySnapshotRecord(models.Model):
    uid = models.BigAutoField(primary_key=True)

    application_name = models.CharField(max_length=32, help_text=_("Application name."))
    originator_id = models.UUIDField(
        help_text=_("Originator ID (e.g. an entity or aggregate ID).")
    )
    originator_version = models.BigIntegerField(
        help_text=_("Originator version of item in sequence.")
    )
    topic = models.TextField(
        help_text=_("Topic of the item (e.g. path to domain event class).")
    )
    state = models.BinaryField(
        help_text=_("State of the item (serialized dict, possibly encrypted).")
    )

    class Meta:
        abstract = True
        unique_together = (("application_name", "originator_id", "originator_version"),)


class AbstractStoredEventRecord(models.Model):
    uid = models.BigAutoField(primary_key=True)

    application_name = models.CharField(max_length=32, help_text=_("Application name."))
    originator_id = models.UUIDField(
        help_text=_("Originator ID (e.g. an entity or aggregate ID).")
    )
    originator_version = models.BigIntegerField(
        help_text=_("Originator version of item in sequence.")
    )
    pipeline_id = models.IntegerField(help_text=_("Pipeline ID."))
    notification_id = models.BigIntegerField(help_text=_("Notification ID."))
    topic = models.TextField(
        help_text=_("Topic of the item (e.g. path to domain event class).")
    )
    state = models.BinaryField(
        help_text=_("State of the item (serialized dict, possibly encrypted).")
    )
    causal_dependencies = models.TextField(help_text=_("Causal dependencies."))

    class Meta:
        abstract = True
        unique_together = (
            ("application_name", "originator_id", "originator_version"),
            ("application_name", "pipeline_id", "notification_id"),
        )


class AbstractNotificationTrackingRecord(models.Model):
    uid = models.BigAutoField(
        primary_key=True, help_text=_("Position (timestamp) of item in sequence.")
    )

    application_name = models.CharField(max_length=32, help_text=_("Application name."))
    upstream_application_name = models.CharField(
        max_length=32, help_text=_("Upstream application name.")
    )
    pipeline_id = models.IntegerField(help_text=_("Pipeline ID."))
    notification_id = models.BigIntegerField(help_text=_("Notification ID."))

    class Meta:
        abstract = True
        unique_together = (
            (
                "application_name",
                "upstream_application_name",
                "pipeline_id",
                "notification_id",
            ),
        )


ABSTRACT_MODELS = (
    AbstractEntitySnapshotRecord,
    AbstractIntegerSequencedRecord,
    AbstractNotificationTrackingRecord,
    AbstractSnapshotRecord,
    AbstractStoredEventRecord,
    AbstractTimestampSequencedRecord,
)
