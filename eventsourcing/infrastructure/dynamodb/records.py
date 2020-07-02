import os
from decimal import Decimal

from pynamodb.attributes import (
    BinaryAttribute,
    NumberAttribute,
    UnicodeAttribute,
)
from pynamodb.models import Model

from eventsourcing.infrastructure.dynamodb.attributes import (
    DecimalAttribute,
    UUIDAttribute,
)


class PynamoDbModelWithAWSConfig(Model):
    """
    Wrapper around core PynamoDB model with AWS configuration.
    """

    class Meta(Model):
        read_capacity_units = 1   # for table creation
        write_capacity_units = 1  # for table creation
        host = os.getenv('DYNAMODB_HOST', default=None)
        region = os.getenv('AWS_REGION')
        aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
        aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        aws_session_token = os.getenv('AWS_SESSION_TOKEN')


class DecimalTypeRangeKeyConditionMixin:
    """
    Mixin for defining decimal-related meta attributes.

    These are used when computing start/end indices for DynamoDB's
    BETWEEN range key condition. This mixin should typically be used
    in conjunction with records that require a floating or
    timestamp-based range index.
    """

    class Meta:
        range_type = Decimal
        range_delta = 1e-06  # e.g. 1 microsecond


class IntegerSequencedRecord(PynamoDbModelWithAWSConfig):
    """Stores integer-sequenced items in DynamoDB."""

    class Meta(PynamoDbModelWithAWSConfig.Meta):
        table_name = "integer_sequenced_items"

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = UUIDAttribute(hash_key=True)

    # Position (index) of item in sequence.
    position = NumberAttribute(range_key=True)

    # Topic of the item (e.g. path to domain event class).
    topic = UnicodeAttribute(null=False)

    # State of the item (serialized dict, possibly encrypted).
    state = BinaryAttribute(null=False)


class TimestampSequencedRecord(PynamoDbModelWithAWSConfig):
    """Stores timestamp-sequenced items in DynamoDB."""

    class Meta(
        DecimalTypeRangeKeyConditionMixin.Meta,
        PynamoDbModelWithAWSConfig.Meta,
    ):
        table_name = "timestamp_sequenced_items"

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = UUIDAttribute(hash_key=True)

    # Position (in time) of item in sequence.
    position = DecimalAttribute(range_key=True)

    # Topic of the item (e.g. path to domain event class).
    topic = UnicodeAttribute(null=False)

    # State of the item (serialized dict, possibly encrypted).
    state = BinaryAttribute(null=False)


class SnapshotRecord(PynamoDbModelWithAWSConfig):
    """Stores snapshots in DynamoDB."""

    class Meta(PynamoDbModelWithAWSConfig.Meta):
        table_name = "snapshots"

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = UUIDAttribute(hash_key=True)

    # Position (index) of item in sequence.
    position = NumberAttribute(range_key=True)

    # Topic of the item (e.g. path to domain event class).
    topic = UnicodeAttribute(null=False)

    # State of the entity (serialized dict, possibly encrypted).
    state = BinaryAttribute(null=False)


class EntitySnapshotRecord(PynamoDbModelWithAWSConfig):
    """Stores entity snapshots in DynamoDB."""

    class Meta(PynamoDbModelWithAWSConfig.Meta):
        table_name = "entity_snapshots"

    # Application ID.
    application_name = UnicodeAttribute(null=False)

    # Originator ID (e.g. an entity or aggregate UUID).
    originator_id = UUIDAttribute(hash_key=True)

    # Originator version of item in sequence.
    originator_version = NumberAttribute(range_key=True)

    # Topic of the item (e.g. path to domain entity class).
    topic = UnicodeAttribute(null=False)

    # State of the item (serialized dict, possibly encrypted).
    state = BinaryAttribute(null=False)


class StoredEventRecord(PynamoDbModelWithAWSConfig):
    """Stores integer-sequenced items in DynamoDB."""

    class Meta(PynamoDbModelWithAWSConfig.Meta):
        table_name = "stored_events"

    # Aggregate UUID (e.g. an entity or aggregate UUID).
    originator_id = UUIDAttribute(hash_key=True)

    # Aggregate version (index) of item in sequence.
    originator_version = NumberAttribute(range_key=True)

    # Notification ID.
    notification_id = NumberAttribute(null=True)

    # Topic of the item (e.g. path to domain event class).
    topic = UnicodeAttribute(null=False)

    # State of the item (serialized dict, possibly encrypted).
    state = BinaryAttribute(null=False)
