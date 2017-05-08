import six
from cassandra.cqlengine.functions import Token
from cassandra.cqlengine.models import columns
from cassandra.cqlengine.query import BatchQuery, LWTException

from eventsourcing.infrastructure.activerecord import AbstractActiveRecordStrategy
from eventsourcing.infrastructure.cassandra.datastore import ActiveRecord


class CassandraActiveRecordStrategy(AbstractActiveRecordStrategy):
    def append(self, sequenced_item_or_items):
        if isinstance(sequenced_item_or_items, list):
            if len(sequenced_item_or_items):
                b = BatchQuery()
                for item in sequenced_item_or_items:
                    assert isinstance(item, self.sequenced_item_class), (type(item), self.sequenced_item_class)
                    kwargs = self.get_field_kwargs(item)
                    self.active_record_class.batch(b).if_not_exists().create(**kwargs)
                try:
                    b.execute()
                except LWTException as e:
                    self.raise_sequenced_item_error(sequenced_item_or_items, e)
        else:
            active_record = self.to_active_record(sequenced_item_or_items)
            try:
                active_record.save()
            except LWTException as e:
                self.raise_sequenced_item_error(sequenced_item_or_items, e)

    def get_item(self, sequence_id, eq):
        kwargs = {
            self.field_names.sequence_id: sequence_id,
            '{}__eq'.format(self.field_names.position): eq
        }
        query = self.filter(**kwargs)
        items = six.moves.map(self.from_active_record, query)
        items = list(items)
        try:
            return items[0]
        except IndexError:
            self.raise_index_error(eq)

    def get_items(self, sequence_id, gt=None, gte=None, lt=None, lte=None, limit=None,
                  query_ascending=True, results_ascending=True):

        assert limit is None or limit >= 1, limit
        assert not (gte and gt)
        assert not (lte and lt)

        kwargs = {self.field_names.sequence_id: sequence_id}
        query = self.filter(**kwargs)

        if query_ascending:
            query = query.order_by(self.field_names.position)

        position_name = self.field_names.position
        if gt is not None:
            kwargs = {'{}__gt'.format(position_name): gt}
            query = query.filter(**kwargs)
        if gte is not None:
            kwargs = {'{}__gte'.format(position_name): gte}
            query = query.filter(**kwargs)
        if lt is not None:
            kwargs = {'{}__lt'.format(position_name): lt}
            query = query.filter(**kwargs)
        if lte is not None:
            kwargs = {'{}__lte'.format(position_name): lte}
            query = query.filter(**kwargs)

        if limit is not None:
            query = query.limit(limit)

        items = six.moves.map(self.from_active_record, query)

        items = list(items)

        if results_ascending != query_ascending:
            items.reverse()

        return items

    def all_items(self):
        for record in self.all_records():
            yield self.from_active_record(record)

    def all_records(self):
        query = self.active_record_class.objects.all().limit(10)
        page = list(query)
        while page:
            for record in page:
                yield record
            last = page[-1]
            page = list(query.filter(pk__token__gt=Token(last.pk)))

    def delete_record(self, record):
        assert isinstance(record, self.active_record_class)
        record.delete()

    def to_active_record(self, sequenced_item):
        """
        Returns an active record instance, from given sequenced item.
        """
        assert isinstance(sequenced_item, self.sequenced_item_class), (type(sequenced_item), self.sequenced_item_class)
        kwargs = self.get_field_kwargs(sequenced_item)
        return self.active_record_class(**kwargs)

    def from_active_record(self, active_record):
        """
        Returns a sequenced item instance, from given active record.
        """
        kwargs = self.get_field_kwargs(active_record)
        return self.sequenced_item_class(**kwargs)

    def filter(self, *args, **kwargs):
        return self.active_record_class.objects.filter(*args, **kwargs)


class IntegerSequencedItemRecord(ActiveRecord):
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
    data = columns.Text(required=True)


class TimestampSequencedItemRecord(ActiveRecord):
    """Stores timestamp-sequenced items in Cassandra."""
    __table_name__ = 'timestamp_sequenced_items'
    _if_not_exists = True

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = columns.UUID(partition_key=True)

    # Position (in time) of item in sequence.
    position = columns.Double(clustering_order='DESC', primary_key=True)

    # Topic of the item (e.g. path to domain event class).
    topic = columns.Text(required=True)

    # State of the item (serialized dict, possibly encrypted).
    data = columns.Text(required=True)


class CqlTimeuuidSequencedItem(ActiveRecord):
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
    data = columns.Text(required=True)


class SnapshotRecord(ActiveRecord):
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
    data = columns.Text(required=True)
