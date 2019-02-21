import os
from cassandra import InvalidRequest
from cassandra.cqlengine.functions import Token
from cassandra.cqlengine.query import BatchQuery, LWTException

from eventsourcing.exceptions import ProgrammingError
from eventsourcing.infrastructure.base import AbstractSequencedItemRecordManager


class CassandraRecordManager(AbstractSequencedItemRecordManager):
    def record_sequenced_items(self, sequenced_item_or_items):
        if isinstance(sequenced_item_or_items, list):
            if len(sequenced_item_or_items):
                b = BatchQuery()
                for item in sequenced_item_or_items:
                    assert isinstance(item, self.sequenced_item_class), (type(item), self.sequenced_item_class)
                    kwargs = self.get_field_kwargs(item)
                    self.record_class.batch(b).if_not_exists().create(**kwargs)
                try:
                    b.execute()
                except LWTException:
                    self.raise_sequenced_item_conflict()
        else:
            record = self.to_record(sequenced_item_or_items)
            try:
                record.save()
            except LWTException:
                self.raise_sequenced_item_conflict()

    def get_record(self, sequence_id, position):
        kwargs = {
            self.field_names.sequence_id: sequence_id,
            '{}__eq'.format(self.field_names.position): position
        }
        query = self.filter(**kwargs)
        try:
            record = list(query)[0]
        except IndexError:
            self.raise_index_error(position)
        return record

    def get_records(self, sequence_id, gt=None, gte=None, lt=None, lte=None, limit=None,
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

        items = list(query)

        if results_ascending != query_ascending:
            items.reverse()

        return items

    def get_notifications(self, start=None, stop=None, *args, **kwargs):
        """Not implemented."""

    def all_sequence_ids(self):
        sequence_id_page_size = int(os.getenv('SEQUENCE_ID_PAGE_SIZE') or '1')
        assert sequence_id_page_size > 0, sequence_id_page_size
        query = self.record_class.objects.all().limit(sequence_id_page_size)

        page = list(query)
        # # Resume if possible.
        # if resume is None:
        #     page = list(query)
        # else:
        #     page = list(query.filter(pk__token__gt=Token(resume)))

        while page:
            for record in page:
                yield record.pk
            last = page[-1]
            page = list(query.filter(pk__token__gt=Token(last.pk)))

    def delete_record(self, record):
        assert isinstance(record, self.record_class), type(record)
        try:
            record.delete()
        except InvalidRequest as e:
            raise ProgrammingError(e)

    def filter(self, **kwargs):
        return self.record_class.objects.filter(**kwargs)
