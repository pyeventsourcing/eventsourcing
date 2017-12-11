import six
from django.db import IntegrityError, transaction

from eventsourcing.exceptions import SequencedItemConflict
from eventsourcing.infrastructure.activerecord import AbstractActiveRecordStrategy


class DjangoActiveRecordStrategy(AbstractActiveRecordStrategy):
    def __init__(self, *args, **kwargs):
        super(DjangoActiveRecordStrategy, self).__init__(*args, **kwargs)

    def append(self, sequenced_item_or_items):
        # Convert sequenced item(s) to active_record(s).
        if isinstance(sequenced_item_or_items, list):
            active_records = [self.to_active_record(i) for i in sequenced_item_or_items]
        else:
            active_records = [self.to_active_record(sequenced_item_or_items)]
        try:
            with transaction.atomic():
                self.active_record_class.objects.bulk_create(active_records)
        except IntegrityError as e:
            raise SequencedItemConflict(e)

    def get_item(self, sequence_id, eq):
        try:
            records = self.active_record_class.objects.filter(sequence_id=sequence_id, position=eq).all()
        except self.active_record_class.DoesNotExist:
            raise IndexError
        else:
            if len(records) != 1:
                raise IndexError(len(records))
            return self.from_active_record(records[0])

    def get_items(self, sequence_id, gt=None, gte=None, lt=None, lte=None, limit=None,
                  query_ascending=True, results_ascending=True):
        #
        assert limit is None or limit >= 1, limit

        filter_kwargs = {self.field_names.sequence_id: sequence_id}
        query = self.active_record_class.objects.filter(**filter_kwargs)

        position_field_name = self.field_names.position

        if query_ascending:
            query = query.order_by(position_field_name)
        else:
            query = query.order_by('-'+position_field_name)

        if gt is not None:
            arg = '{}__gt'.format(position_field_name)
            query = query.filter(**{arg: gt})
        if gte is not None:
            arg = '{}__gte'.format(position_field_name)
            query = query.filter(**{arg: gte})
        if lt is not None:
            arg = '{}__lt'.format(position_field_name)
            query = query.filter(**{arg: lt})
        if lte is not None:
            arg = '{}__lte'.format(position_field_name)
            query = query.filter(**{arg: lte})

        if limit is not None:
            query = query[:limit]

        results = query.all()

        if results_ascending != query_ascending:
            # This code path is under test, but not otherwise used ATM.
            results = list(results)
            results.reverse()

        for item in six.moves.map(self.from_active_record, results):
            yield item

    def to_active_record(self, sequenced_item):
        """
        Returns an active record, from given sequenced item.
        """
        # Check we got a sequenced item.
        assert isinstance(sequenced_item, self.sequenced_item_class), (self.sequenced_item_class, type(sequenced_item))

        # Construct and return an ORM object.
        kwargs = self.get_field_kwargs(sequenced_item)
        return self.active_record_class(**kwargs)

    def all_items(self):
        """
        Returns all items across all sequences.
        """
        return six.moves.map(self.from_active_record, self.all_records())

    def from_active_record(self, active_record):
        """
        Returns a sequenced item, from given active record.
        """
        kwargs = self.get_field_kwargs(active_record)
        return self.sequenced_item_class(**kwargs)

    def all_records(self, *args, **kwargs):
        """
        Returns all records in the table.
        """
        return self.active_record_class.objects.all()

    def delete_record(self, record):
        """
        Permanently removes record from table.
        """
        pass
        # try:
        #     self.session.delete(record)
        #     self.session.commit()
        # except Exception as e:
        #     self.session.rollback()
        #     raise ProgrammingError(e)
        # finally:
        #     self.session.close()
