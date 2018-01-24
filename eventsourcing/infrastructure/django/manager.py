from decimal import Decimal

import six
from django.db import IntegrityError, connection, transaction

from eventsourcing.infrastructure.base import RelationalRecordManager


class DjangoRecordManager(RelationalRecordManager):
    def __init__(self, convert_position_float_to_decimal=False, *args, **kwargs):
        # Somehow when the Decimal converter is registered with sqlite3,
        # decimal values that are stored successfully with 6 places are
        # returned as bytes rounded to 5 places, before being converted
        # to a Decimal. Somehow the bytes passed to the converter has
        # less than the float received without a converter being registered.
        # So to get 6 places, suspend the converter, and convert to Decimal
        # by using the accurate float value as a str to make a Decimal. Don't
        # know why sqlite3 rounds the float when passing bytes to the converter.
        # Django registers converter in django.db.backends.sqlite3.base line 42
        # in Django v2.0.0. The sqlite3 library behaves in the same way when Django
        # is not involved, so there's nothing that Django is doing to break sqlite3.
        # And the reason SQLAlchemy works is because it doesn't register converters,
        # but rather manages the conversion to Decimal itself.
        # If the converter is cancelled, Decimal position values
        # are returned by Django as floats with original
        # accuracy so we just need to convert them to Decimal
        # values. The retrieved position values are not
        # used at all, and in all cases appear to be written in
        # the database with original precision, this issue only
        # affects one of the library's test cases, which should
        # perhaps be changed to avoid checking retrieved positions.
        self.convert_position_float_to_decimal = convert_position_float_to_decimal
        super(DjangoRecordManager, self).__init__(*args, **kwargs)

    def _write_records(self, records):
        try:
            with transaction.atomic(self.record_class.objects.db):
                if self.contiguous_record_ids:
                    # Use cursor to execute insert select max statement.
                    with connection.cursor() as cursor:
                        for record in records:
                            # Get values from record obj.
                            params = []
                            for col_name in self.field_names:
                                col_value = getattr(record, col_name)
                                col_type = self.record_class._meta.get_field(col_name)

                                # Prepare value for database.
                                param = col_type.get_db_prep_value(col_value, connection)
                                params.append(param)

                            # Execute insert statement.
                            cursor.execute(self.insert_select_max, params)
                else:
                    # Todo: If it's faster, change to use an "insert_values" raw query.
                    # Save record objects.
                    for record in records:
                        record.save()

        except IntegrityError as e:
            self.raise_after_integrity_error(e)

    def _prepare_insert(self, tmpl):
        """
        With transaction isolation level of "read committed" this should
        generate records with a contiguous sequence of integer IDs, using
        an indexed ID column, the database-side SQL max function, the
        insert-select-from form, and optimistic concurrency control.
        """
        statement = tmpl.format(
            tablename=self.record_table_name,
            columns=", ".join(self.field_names),
            placeholders=", ".join(['%s' for _ in self.field_names]),
        )
        return statement

    @property
    def record_table_name(self):
        return self.record_class._meta.db_table

    def get_item(self, sequence_id, eq):
        records = self.record_class.objects.filter(sequence_id=sequence_id, position=eq).all()
        return self.from_record(records[0])

    def get_records(self, sequence_id, gt=None, gte=None, lt=None, lte=None, limit=None,
                    query_ascending=True, results_ascending=True):

        assert limit is None or limit >= 1, limit

        filter_kwargs = {self.field_names.sequence_id: sequence_id}
        query = self.record_class.objects.filter(**filter_kwargs)

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

        records = query.all()

        if results_ascending != query_ascending:
            # This code path is under test, but not otherwise used ATM.
            records = list(records)
            records.reverse()

        return records

    def all_items(self):
        """
        Returns all items across all sequences.
        """
        return six.moves.map(self.from_record, self.all_records())

    def get_field_kwargs(self, record):
        # Need to convert floats to decimals if Django's sqlite3
        # Decimal converter has been cancelled. Which it is in
        # the test for this class, so that the positions
        # can be checked accurately.
        kwargs = super(DjangoRecordManager, self).get_field_kwargs(record)
        if self.convert_position_float_to_decimal:
            position_field_name = self.field_names.position
            position_value = kwargs[position_field_name]
            if isinstance(position_value, float):
                # Somehow this gets used on my laptop, but not on Travis...
                kwargs[position_field_name] = Decimal(str(position_value))

        return kwargs

    def all_records(self, start=None, stop=None, *args, **kwargs):
        """
        Returns all records in the table.
        """
        filter_kwargs = {}
        position_field_name = 'id'
        # Todo: Also support sequencing by 'position' if items are sequenced by timestamp?
        if start is not None:
            filter_kwargs['%s__gte' % position_field_name] = start + 1
        if stop is not None:
            filter_kwargs['%s__lt' % position_field_name] = stop + 1
        query = self.record_class.objects.filter(**filter_kwargs)
        query = query.order_by('%s' % position_field_name)
        return query.all()

    def delete_record(self, record):
        """
        Permanently removes record from table.
        """
        record.delete()

    def get_max_record_id(self):
        try:
            return self.record_class.objects.latest('id').id
        except self.record_class.DoesNotExist:
            return None
