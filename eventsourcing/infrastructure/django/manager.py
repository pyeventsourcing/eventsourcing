import six
from django.db import IntegrityError, connection, transaction

from eventsourcing.infrastructure.base import RelationalRecordManager


class DjangoRecordManager(RelationalRecordManager):
    def __init__(self, *args, **kwargs):
        super(DjangoRecordManager, self).__init__(*args, **kwargs)

    def _write_records(self, records, tracking_kwargs=None):
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
            self.raise_record_integrity_error(e)

    def _prepare_insert(self, tmpl, record_class, field_names, placeholder_for_id=False):
        """
        With transaction isolation level of "read committed" this should
        generate records with a contiguous sequence of integer IDs, using
        an indexed ID column, the database-side SQL max function, the
        insert-select-from form, and optimistic concurrency control.
        """
        statement = tmpl.format(
            tablename=self.get_record_table_name(record_class),
            columns=", ".join(field_names),
            placeholders=", ".join(['%s' for _ in field_names]),
        )
        return statement

    def get_record_table_name(self, record_class):
        """Returns table name from SQLAlchemy record class."""
        return record_class._meta.db_table

    def get_item(self, sequence_id, position):
        records = self.record_class.objects.filter(sequence_id=sequence_id, position=position).all()
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

    def get_notifications(self, start=None, stop=None, *args, **kwargs):
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

    def all_sequence_ids(self):
        sequence_id_fieldname = self.field_names.sequence_id
        values_queryset = self.record_class.objects.values(sequence_id_fieldname).distinct()
        for values in values_queryset:
            yield values[sequence_id_fieldname]
