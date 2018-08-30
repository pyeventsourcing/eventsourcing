from django.db import IntegrityError, connection, transaction, ProgrammingError

from eventsourcing.infrastructure.base import SQLRecordManager
from eventsourcing.infrastructure.django.models import NotificationTrackingRecord


class DjangoRecordManager(SQLRecordManager):
    tracking_record_class = NotificationTrackingRecord

    _where_application_name_tmpl = (
        " WHERE application_name = %s AND pipeline_id = %s"
    )

    def write_records(self, records, tracking_kwargs=None):
        try:
            with transaction.atomic(self.record_class.objects.db):
                with connection.cursor() as cursor:
                    if tracking_kwargs:
                        # Insert tracking record.
                        params = [tracking_kwargs[c] for c in self.tracking_record_field_names]
                        cursor.execute(self.insert_tracking_record, params)

                    if self.contiguous_record_ids:
                        # Use cursor to execute insert select max statement.
                        for record in records:
                            # Get values from record obj.
                            # List of params, because dict doesn't work with Django and SQLite.
                            params = []

                            for col_name in self.field_names:
                                col_value = getattr(record, col_name)
                                col_type = self.record_class._meta.get_field(col_name)

                                # Prepare value for database.
                                param = col_type.get_db_prep_value(col_value, connection)
                                params.append(param)

                            # Notification logs fields, to be inserted with event fields.
                            if hasattr(self.record_class, 'application_name'):
                                params.append(self.application_name)
                            if hasattr(self.record_class, 'pipeline_id'):
                                params.append(self.pipeline_id)
                            if hasattr(record, 'causal_dependencies'):
                                params.append(record.causal_dependencies)

                            # Where clause fields.
                            if hasattr(self.record_class, 'application_name'):
                                params.append(self.application_name)
                            if hasattr(self.record_class, 'pipeline_id'):
                                params.append(self.pipeline_id)

                            # Execute insert statement.
                            cursor.execute(self.insert_select_max, params)
                            # Todo: Use insert_values when records have IDs (like SQLAlchemy manager).
                            # Todo: Support 'event-not-notifiable' by setting pipeline ID and notification ID to None.

                    else:
                        # This can only work for simple models, without application_name
                        # and pipeline_id, because it relies on the auto-incrementing ID.
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
        field_names = list(field_names)
        if hasattr(record_class, 'application_name') and 'application_name' not in field_names:
            field_names.append('application_name')
        if hasattr(record_class, 'pipeline_id') and 'pipeline_id' not in field_names:
            field_names.append('pipeline_id')
        if hasattr(record_class, 'causal_dependencies') and 'causal_dependencies' not in field_names:
            field_names.append('causal_dependencies')
        if placeholder_for_id:
            if self.notification_id_name:
                if self.notification_id_name not in field_names:
                    field_names.append('id')

        statement = tmpl.format(
            tablename=self.get_record_table_name(record_class),
            columns=", ".join(field_names),
            placeholders=", ".join(['%s' for _ in field_names]),
            notification_id=self.notification_id_name
        )
        return statement

    def get_record_table_name(self, record_class):
        """Returns table name from SQLAlchemy record class."""
        return record_class._meta.db_table

    def get_record(self, sequence_id, position):
        kwargs = {
            self.field_names.sequence_id: sequence_id,
            self.field_names.position: position,
        }
        records = self.record_class.objects.filter(**kwargs)
        # Todo: try/except for native error here, call self.raise_index_error()
        return records.all()[0]

    def get_records(self, sequence_id, gt=None, gte=None, lt=None, lte=None, limit=None,
                    query_ascending=True, results_ascending=True):

        assert limit is None or limit >= 1, limit

        filter_kwargs = {self.field_names.sequence_id: sequence_id}
        objects = self.record_class.objects.filter(**filter_kwargs)

        if hasattr(self.record_class, 'application_name'):
            objects = objects.filter(application_name=self.application_name)

        position_field_name = self.field_names.position

        if query_ascending:
            objects = objects.order_by(position_field_name)
        else:
            objects = objects.order_by('-' + position_field_name)

        if gt is not None:
            arg = '{}__gt'.format(position_field_name)
            objects = objects.filter(**{arg: gt})
        if gte is not None:
            arg = '{}__gte'.format(position_field_name)
            objects = objects.filter(**{arg: gte})
        if lt is not None:
            arg = '{}__lt'.format(position_field_name)
            objects = objects.filter(**{arg: lt})
        if lte is not None:
            arg = '{}__lte'.format(position_field_name)
            objects = objects.filter(**{arg: lte})

        if limit is not None:
            objects = objects[:limit]

        records = objects.all()

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
        # Todo: Also support sequencing by 'position' if items are sequenced by timestamp?
        if start is not None:
            filter_kwargs['%s__gte' % self.notification_id_name] = start + 1
        if stop is not None:
            filter_kwargs['%s__lt' % self.notification_id_name] = stop + 1
        objects = self.record_class.objects.filter(**filter_kwargs)

        if hasattr(self.record_class, 'application_name'):
            objects = objects.filter(application_name=self.application_name)
        if hasattr(self.record_class, 'pipeline_id'):
            objects = objects.filter(pipeline_id=self.pipeline_id)

        objects = objects.order_by('%s' % self.notification_id_name)
        return objects.all()

    def delete_record(self, record):
        """
        Permanently removes record from table.
        """
        record.delete()

    def get_max_record_id(self):
        assert self.notification_id_name
        try:
            objects = self.record_class.objects
            if hasattr(self.record_class, 'application_name'):
                objects = objects.filter(application_name=self.application_name)
            if hasattr(self.record_class, 'pipeline_id'):
                objects = objects.filter(pipeline_id=self.pipeline_id)
            latest = objects.latest(self.notification_id_name)
            return getattr(latest, self.notification_id_name)
        except (self.record_class.DoesNotExist, ProgrammingError):
            return None

    def get_max_tracking_record_id(self, upstream_application_name):
        notification_id = None
        try:
            objects = self.tracking_record_class.objects
            objects = objects.filter(application_name=self.application_name)
            objects = objects.filter(upstream_application_name=upstream_application_name)
            objects = objects.filter(pipeline_id=self.pipeline_id)
            notification_id = objects.latest('notification_id').notification_id
        except self.tracking_record_class.DoesNotExist:
            pass
        return notification_id

    def has_tracking_record(self, upstream_application_name, pipeline_id, notification_id):
        objects = self.tracking_record_class.objects
        objects = objects.filter(application_name=self.application_name)
        objects = objects.filter(upstream_application_name=upstream_application_name)
        objects = objects.filter(pipeline_id=pipeline_id)
        objects = objects.filter(notification_id=notification_id)
        return bool(objects.count())

    def all_sequence_ids(self):
        sequence_id_fieldname = self.field_names.sequence_id
        values_queryset = self.record_class.objects.values(sequence_id_fieldname).distinct()
        for values in values_queryset:
            yield values[sequence_id_fieldname]
