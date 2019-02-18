from cassandra.cqlengine.models import columns, Model


class IntegerSequencedRecord(Model):
    """Stores integer-sequenced items in Cassandra."""
    __table_name__ = 'integer_sequenced_items'
    _if_not_exists = True

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = columns.UUID(partition_key=True)

    # Position (index) of item in sequence.
    position = columns.BigInt(clustering_order='DESC', primary_key=True)

    # Topic of the item (e.g. path to domain event class).
    topic = columns.Text(required=True)

    # State of the item (serialized dict, possibly encrypted).
    state = columns.Text(required=True)


class TimestampSequencedRecord(Model):
    """Stores timestamp-sequenced items in Cassandra."""
    __table_name__ = 'timestamp_sequenced_items'
    _if_not_exists = True

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = columns.UUID(partition_key=True)

    # Position (in time) of item in sequence.
    position = columns.Decimal(clustering_order='DESC', primary_key=True)

    # Topic of the item (e.g. path to domain event class).
    topic = columns.Text(required=True)

    # State of the item (serialized dict, possibly encrypted).
    state = columns.Text(required=True)


class TimeuuidSequencedRecord(Model):
    """Stores timeuuid-sequenced items in Cassandra."""
    __table_name__ = 'timeuuid_sequenced_items'
    _if_not_exists = True

    # Sequence UUID (e.g. an entity or aggregate ID).
    sequence_id = columns.UUID(partition_key=True)

    # Position (in time) of item in sequence.
    position = columns.TimeUUID(clustering_order='DESC', primary_key=True)

    # Topic of the item (e.g. path to domain event class).
    topic = columns.Text(required=True)

    # State of the item (serialized dict, possibly encrypted).
    state = columns.Text(required=True)


class SnapshotRecord(Model):
    """Stores snapshots in Cassandra."""
    __table_name__ = 'snapshots'
    _if_not_exists = True

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = columns.UUID(partition_key=True)

    # Position (index) of item in sequence.
    position = columns.BigInt(clustering_order='DESC', primary_key=True)

    # Topic of the item (e.g. path to domain entity class).
    topic = columns.Text(required=True)

    # State of the entity (serialized dict, possibly encrypted).
    state = columns.Text(required=True)


class StoredEventRecord(Model):
    """Stores integer-sequenced items in Cassandra."""
    __table_name__ = 'stored_events'
    _if_not_exists = True

    # Aggregate ID (e.g. an entity or aggregate ID).
    originator_id = columns.UUID(partition_key=True)

    # Aggregate version (index) of item in sequence.
    originator_version = columns.BigInt(clustering_order='DESC', primary_key=True)

    # Topic of the item (e.g. path to domain event class).
    topic = columns.Text(required=True)

    # State of the item (serialized dict, possibly encrypted).
    state = columns.Text(required=True)
