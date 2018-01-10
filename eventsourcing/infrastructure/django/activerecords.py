from decimal import Decimal

import six
from django.db import IntegrityError, OperationalError, transaction

from eventsourcing.exceptions import ProgrammingError, SequencedItemConflict
from eventsourcing.infrastructure.relationalactiverecordstrategy import RelationalActiveRecordStrategy


class DjangoActiveRecordStrategy(RelationalActiveRecordStrategy):
    def __init__(self, cancel_sqlite3_decimal_converter=False, *args, **kwargs):
        self.cancel_sqlite3_decimal_converter = cancel_sqlite3_decimal_converter
        super(DjangoActiveRecordStrategy, self).__init__(*args, **kwargs)

        # Somehow when the Decimal converter is registered with sqlite3,
        # decimal values that are stored successfully with 6 places are
        # returned as bytes rounded to 5 places, before being converted
        # to a Decimal. Somehow the bytes passed to the converter has
        # less than the float received without a converter being registered.
        # So to get 6 places, suspend the converter, and convert to Decimal
        # by using the accurate float value as a str to make a Decimal. So
        # how does sqlite3 round the float when passing bytes to the converter?
        # Django registers converter in django.db.backends.sqlite3.base line 42
        # in Django v2.0.0. The sqlite3 library behaves in the same way when Django
        # is not involved, so there's nothing that Django is doing to break sqlite3.
        # And the reason SQLAlchemy works is because it doesn't register converters,
        # but rather manages the conversion to Decimal itself.
        if self.cancel_sqlite3_decimal_converter:
            import sqlite3
            sqlite3.register_converter("decimal", None)

    def _write_active_records(self, active_records, sequenced_items):
        try:
            with transaction.atomic():
                self.active_record_class.objects.bulk_create(active_records)
        except IntegrityError as e:
            raise SequencedItemConflict(e)

    def get_item(self, sequence_id, eq):
        records = self.active_record_class.objects.filter(sequence_id=sequence_id, position=eq).all()
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
            query = query.order_by('-' + position_field_name)

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

    # def filter(self, **kwargs):
    #     pass
    #     # return self.query.filter_by(**kwargs)

    # @property
    # def query(self):
    #     pass
    #     # return self.session.query(self.active_record_class)

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

        # Does this if the Django sqlite3 Decimal converter has been cancelled.
        if self.cancel_sqlite3_decimal_converter:
            position_field_name = self.field_names.position
            if isinstance(kwargs[position_field_name], float):
                kwargs[position_field_name] = Decimal(str(kwargs[position_field_name]))

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
        try:
            record.delete()
        except OperationalError:
            raise ProgrammingError
