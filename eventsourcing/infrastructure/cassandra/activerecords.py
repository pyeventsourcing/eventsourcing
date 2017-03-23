import six
from cassandra.cqlengine.models import Model, columns
from cassandra.cqlengine.query import LWTException, BatchQuery

from eventsourcing.infrastructure.activerecord import AbstractActiveRecordStrategy


class CassandraActiveRecordStrategy(AbstractActiveRecordStrategy):

    def append_item(self, sequenced_item):
        if isinstance(sequenced_item, list):
            with BatchQuery() as b:
                for i in sequenced_item:
                    assert isinstance(i, self.sequenced_item_class), (type(i), self.sequenced_item_class)
                    self.active_record_class.batch(b).create(
                        s=i.sequence_id,
                        p=i.position,
                        t=i.topic,
                        d=i.data,
                    )
        else:
            active_record = self._to_active_record(sequenced_item)
            try:
                active_record.save()
            except LWTException as e:
                self.raise_sequence_item_error(sequenced_item.sequence_id, sequenced_item.position, e)

    def get_item(self, sequence_id, eq):
        query = self._filter(s=sequence_id, p__eq=eq)
        items = six.moves.map(self._from_active_record, query)
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

        query = self._filter(s=sequence_id)

        if query_ascending:
            query = query.order_by('p')

        if gt is not None:
            query = query.filter(p__gt=gt)
        if gte is not None:
            query = query.filter(p__gte=gte)
        if lt is not None:
            query = query.filter(p__lt=lt)
        if lte is not None:
            query = query.filter(p__lte=lte)

        if limit is not None:
            query = query.limit(limit)

        items = six.moves.map(self._from_active_record, query)

        items = list(items)

        if results_ascending != query_ascending:
            items.reverse()

        return items

    def _to_active_record(self, sequenced_item):
        """
        Returns an active record instance, from given sequenced item.
        """
        if isinstance(sequenced_item, list):
            return [self._to_active_record(i) for i in sequenced_item]
        assert isinstance(sequenced_item, self.sequenced_item_class), (type(sequenced_item), self.sequenced_item_class)
        return self.active_record_class(
            s=sequenced_item.sequence_id,
            p=sequenced_item.position,
            t=sequenced_item.topic,
            d=sequenced_item.data
        )

    def _from_active_record(self, active_record):
        """
        Returns a sequenced item instance, from given active record.
        """
        return self.sequenced_item_class(
            sequence_id=active_record.s,
            position=active_record.p,
            topic=active_record.t,
            data=active_record.d,
        )

    def _filter(self, *args, **kwargs):
        return self.active_record_class.objects.filter(*args, **kwargs)


class CqlIntegerSequencedItem(Model):
    """Stores integer-sequenced items in Cassandra."""

    _if_not_exists = True

    __table_name__ = 'integer_sequenced_items'

    # Sequence ID (e.g. an entity or aggregate ID).
    s = columns.UUID(partition_key=True)

    # Position (index) of item in sequence.
    p = columns.BigInt(clustering_order='DESC', primary_key=True)

    # Topic of the item (e.g. path to domain event class).
    t = columns.Text(required=True)

    # State of the item (serialized dict, possibly encrypted).
    d = columns.Text(required=True)


class CqlTimestampSequencedItem(Model):
    """Stores timestamp-sequenced items in Cassandra."""

    _if_not_exists = True

    __table_name__ = 'timestamp_sequenced_items'

    # Sequence ID (e.g. an entity or aggregate ID).
    s = columns.UUID(partition_key=True)

    # Position (in time) of item in sequence.
    p = columns.Double(clustering_order='DESC', primary_key=True)

    # Topic of the item (e.g. path to domain event class).
    t = columns.Text(required=True)

    # State of the item (serialized dict, possibly encrypted).
    d = columns.Text(required=True)


class CqlTimeuuidSequencedItem(Model):
    """Stores timeuuid-sequenced items in Cassandra."""

    _if_not_exists = True

    __table_name__ = 'timeuuid_sequenced_items'

    # Sequence UUID (e.g. an entity or aggregate ID).
    s = columns.UUID(partition_key=True)

    # Position (in time) of item in sequence.
    p = columns.TimeUUID(clustering_order='DESC', primary_key=True)

    # Topic of the item (e.g. path to domain event class).
    t = columns.Text(required=True)

    # State of the item (serialized dict, possibly encrypted).
    d = columns.Text(required=True)
