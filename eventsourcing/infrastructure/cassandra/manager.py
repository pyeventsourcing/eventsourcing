import six
from cassandra import InvalidRequest
from cassandra.cqlengine.functions import Token
from cassandra.cqlengine.query import BatchQuery, LWTException

from eventsourcing.exceptions import ProgrammingError
from eventsourcing.infrastructure.base import AbstractRecordManager


class CassandraRecordManager(AbstractRecordManager):
    def append(self, sequenced_item_or_items):
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

    def get_item(self, sequence_id, eq):
        kwargs = {
            self.field_names.sequence_id: sequence_id,
            '{}__eq'.format(self.field_names.position): eq
        }
        query = self.filter(**kwargs)
        items = six.moves.map(self.from_record, query)
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

        items = six.moves.map(self.from_record, query)

        items = list(items)

        if results_ascending != query_ascending:
            items.reverse()

        return items

    def all_items(self):
        for record in self.all_records():
            sequenced_item = self.from_record(record)
            yield sequenced_item

    def all_records(self, start=None, stop=None, *args, **kwargs):
        position_field_name = self.field_names.position
        for sequence_id in self.all_sequence_ids():
            kwargs = {self.field_names.sequence_id: sequence_id}
            record_query = self.filter(**kwargs).limit(100).order_by(position_field_name)
            record_page = list(record_query)
            while record_page:
                for record in record_page:
                    yield record
                last_record = record_page[-1]
                kwargs = {'{}__gt'.format(position_field_name): getattr(last_record, position_field_name)}
                record_page = list(record_query.filter(**kwargs))

    def all_sequence_ids(self):
        query = self.record_class.objects.all().limit(1)

        # Todo: If there were a resume token, it could be used like this:
        # if resume is None:
        #     page = list(query)
        # else:
        #     page = list(query.filter(pk__token__gt=Token(resume)))
        page = list(query)

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

    def to_record(self, sequenced_item):
        """
        Returns an database record, from given sequenced item.
        """
        assert isinstance(sequenced_item, self.sequenced_item_class), (type(sequenced_item), self.sequenced_item_class)
        kwargs = self.get_field_kwargs(sequenced_item)
        return self.record_class(**kwargs)

    def from_record(self, record):
        """
        Returns a sequenced item instance, from given database record.
        """
        kwargs = self.get_field_kwargs(record)
        return self.sequenced_item_class(**kwargs)

    def filter(self, **kwargs):
        return self.record_class.objects.filter(**kwargs)
