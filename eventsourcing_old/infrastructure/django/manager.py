from typing import Any, Dict, Iterable, Optional, Sequence
from uuid import UUID

import django.db
from django.db import connection, transaction

from eventsourcing.exceptions import ProgrammingError
from eventsourcing.infrastructure.base import (
    EVENT_NOT_NOTIFIABLE,
    SQLRecordManager,
    TrackingKwargs,
)


class DjangoRecordManager(SQLRecordManager):
    _where_application_name_tmpl = " WHERE application_name = %s AND pipeline_id = %s"

    def write_records(
        self,
        records: Iterable[Any],
        tracking_kwargs: Optional[TrackingKwargs] = None,
        orm_objs_pending_save: Optional[Sequence[Any]] = None,
        orm_objs_pending_delete: Optional[Sequence[Any]] = None,
    ) -> None:
        if not isinstance(records, list):
            records = list(records)

        # Prepare tracking params.
        if tracking_kwargs:
            tracking_params = [
                tracking_kwargs[c] for c in self.tracking_record_field_names
            ]
        else:
            tracking_params = None

        use_insert_select_max_statement = False
        event_insert_statement = self.insert_values
        if self.notification_id_name:
            # This is a bit complicated, but basically the idea
            # is to support two alternatives:
            #  - either use the "insert select max" statement
            #  - or use the "insert values" statement
            # The "insert values" statement depends on the
            # notification IDs being provided by the application
            # and the "insert select max" creates these IDs in
            # the query.
            # The "insert values" statement provides the opportunity
            # to have some notification IDs being null, but the
            # "insert select max" statement doesn't.
            # Therefore, using "insert select max" should only be
            # used when all the given records have null value
            # for the notification IDs. And so the alternative
            # usage needs to provide true values for all the
            # notification IDs. These true values can involve
            # a reserved "event-not-notifiable" value which
            # indicates there shouldn't be a notification ID
            # for this record (so that it doesn't appear in the
            # "get notifications" query).
            all_ids = set((getattr(r, self.notification_id_name) for r in records))
            if None in all_ids:
                if len(all_ids) > 1:
                    # Either all or zero records must have IDs.
                    raise ProgrammingError("Only some records have IDs")

                elif self.contiguous_record_ids:
                    # Do an "insert select max" from existing.
                    use_insert_select_max_statement = True
                    event_insert_statement = self.insert_select_max

                elif hasattr(self.record_class, "application_name"):
                    # Can't allow auto-incrementing ID if table has field
                    # application_name. We need values and don't have them.
                    raise ProgrammingError("record ID not set when required")

        if self.contiguous_record_ids:
            all_event_record_params = []
            for record in records:
                # Get values from record obj.
                # List of params, because dict doesn't work with Django
                # and SQLite.
                params = []

                for col_name in self.field_names:
                    col_value = getattr(record, col_name)
                    meta = self.record_class._meta  # type: ignore
                    col_type = meta.get_field(col_name)

                    # Prepare value for database.
                    param = col_type.get_db_prep_value(col_value, connection)
                    params.append(param)

                # Notification logs fields, to be inserted with event
                # fields.
                index_of_pipeline_id_param = None
                if hasattr(self.record_class, "application_name"):
                    params.append(self.application_name)
                if hasattr(self.record_class, "pipeline_id"):
                    params.append(self.pipeline_id)
                    index_of_pipeline_id_param = len(params) - 1
                if hasattr(record, "causal_dependencies"):
                    params.append(record.causal_dependencies)

                if use_insert_select_max_statement:
                    # Where clause fields.
                    if hasattr(self.record_class, "application_name"):
                        params.append(self.application_name)
                    if hasattr(self.record_class, "pipeline_id"):
                        params.append(self.pipeline_id)
                elif self.notification_id_name:
                    if hasattr(self.record_class, self.notification_id_name):
                        notification_id = getattr(record, self.notification_id_name)
                        if notification_id == EVENT_NOT_NOTIFIABLE:
                            notification_id = None
                            params[index_of_pipeline_id_param] = None
                        elif notification_id is not None:
                            if not isinstance(notification_id, int):
                                raise ProgrammingError(
                                    "%s must be an %s not %s: %s"
                                    % (
                                        self.notification_id_name,
                                        int,
                                        type(notification_id),
                                        record.__dict__,
                                    )
                                )

                        params.append(notification_id)

                all_event_record_params.append(params)
        else:
            all_event_record_params = None

        try:
            with transaction.atomic(self.record_class.objects.db):  # type: ignore
                with connection.cursor() as cursor:
                    # Insert tracking record.
                    if tracking_params is not None:
                        cursor.execute(self.insert_tracking_record, tracking_params)

                    if all_event_record_params is not None:
                        for event_record_params in all_event_record_params:
                            # Use cursor to execute event insert statement.
                            cursor.execute(event_insert_statement, event_record_params)

                    else:
                        # This can only work for simple models, without application_name
                        # and pipeline_id, because it relies on the auto-incrementing
                        # ID.
                        # Todo: If it's faster, change to use an "insert_values" raw
                        #  query.
                        # Save record objects.
                        for record in records:
                            record.save()

                    # Call 'save()' on each of the ORM objects pending save.
                    if orm_objs_pending_save:
                        for orm_obj in orm_objs_pending_save:
                            orm_obj.save()

                    # Call 'delete()' on each of the ORM objects pending delete.
                    if orm_objs_pending_delete:
                        for orm_obj in orm_objs_pending_delete:
                            orm_obj.delete()

        except django.db.IntegrityError as e:
            self.raise_record_integrity_error(e)

    def make_placeholder(self, _: str) -> str:
        return "%s"  # doesn't involve field name

    def get_record_table_name(self, record_class: type) -> str:
        """Returns table name from SQLAlchemy record class."""
        return record_class._meta.db_table  # type: ignore

    def get_record(self, sequence_id: UUID, position: int) -> Any:
        kwargs = {
            self.field_names.sequence_id: sequence_id,
            self.field_names.position: position,
        }
        records = self.record_class.objects.filter(**kwargs)  # type: ignore
        # Todo: try/except for native error here, call self.raise_index_error()
        return records.all()[0]

    def get_records(
        self,
        sequence_id: UUID,
        gt: Optional[int] = None,
        gte: Optional[int] = None,
        lt: Optional[int] = None,
        lte: Optional[int] = None,
        limit: Optional[int] = None,
        query_ascending: bool = True,
        results_ascending: bool = True,
    ) -> Sequence[Any]:

        assert limit is None or limit >= 1, limit

        filter_kwargs = {self.field_names.sequence_id: sequence_id}
        objects = self.record_class.objects.filter(**filter_kwargs)  # type: ignore

        if hasattr(self.record_class, "application_name"):
            objects = objects.filter(application_name=self.application_name)

        position_field_name = self.field_names.position

        if query_ascending:
            objects = objects.order_by(position_field_name)
        else:
            objects = objects.order_by("-" + position_field_name)

        if gt is not None:
            arg = "{}__gt".format(position_field_name)
            objects = objects.filter(**{arg: gt})
        if gte is not None:
            arg = "{}__gte".format(position_field_name)
            objects = objects.filter(**{arg: gte})
        if lt is not None:
            arg = "{}__lt".format(position_field_name)
            objects = objects.filter(**{arg: lt})
        if lte is not None:
            arg = "{}__lte".format(position_field_name)
            objects = objects.filter(**{arg: lte})

        if limit is not None:
            objects = objects[:limit]

        records = objects.all()

        if results_ascending != query_ascending:
            # This code path is under test, but not otherwise used ATM.
            records = list(records)
            records.reverse()

        for record in records:
            # Django returns memoryview objects from PostgreSQL, so need to cast.
            state = getattr(record, self.field_names.state)
            setattr(record, self.field_names.state, bytes(state))

        return records

    def get_notification_records(
        self,
        start: Optional[int] = None,
        stop: Optional[int] = None,
        *args: Any,
        **kwargs: Any
    ) -> Iterable:
        """
        Returns all records in the table.
        """
        filter_kwargs = {}
        # Todo: Also support sequencing by 'position' if items are sequenced by
        #  timestamp?
        if start is not None:
            filter_kwargs["%s__gte" % self.notification_id_name] = start + 1
        if stop is not None:
            filter_kwargs["%s__lt" % self.notification_id_name] = stop + 1
        objects = self.record_class.objects.filter(**filter_kwargs)  # type: ignore

        if hasattr(self.record_class, "application_name"):
            objects = objects.filter(application_name=self.application_name)
        if hasattr(self.record_class, "pipeline_id"):
            objects = objects.filter(pipeline_id=self.pipeline_id)

        objects = objects.order_by("%s" % self.notification_id_name)
        for record in objects.all():
            # Django returns memoryview objects from PostgreSQL, so need to cast.
            state = getattr(record, self.field_names.state)
            setattr(record, self.field_names.state, bytes(state))
            yield record

    def delete_record(self, record: Any) -> None:
        """
        Permanently removes record from table.
        """
        record.delete()

    def get_max_notification_id(self) -> int:
        assert self.notification_id_name
        try:
            objects = self.record_class.objects  # type: ignore
            if hasattr(self.record_class, "application_name"):
                objects = objects.filter(application_name=self.application_name)
            if hasattr(self.record_class, "pipeline_id"):
                objects = objects.filter(pipeline_id=self.pipeline_id)
            latest = objects.latest(self.notification_id_name)
            return getattr(latest, self.notification_id_name)
        except self.record_class.DoesNotExist:
            return 0

    def get_max_tracking_record_id(self, upstream_application_name: str) -> int:
        notification_id = 0
        assert self.tracking_record_class is not None
        try:
            objects = self.tracking_record_class.objects  # type: ignore
            objects = objects.filter(application_name=self.application_name)
            objects = objects.filter(
                upstream_application_name=upstream_application_name
            )
            objects = objects.filter(pipeline_id=self.pipeline_id)
            notification_id = objects.latest("notification_id").notification_id
        except self.tracking_record_class.DoesNotExist:  # type: ignore
            pass
        return notification_id

    def has_tracking_record(
        self, upstream_application_name: str, pipeline_id: int, notification_id: int
    ) -> bool:
        objects = self.tracking_record_class.objects  # type: ignore
        objects = objects.filter(application_name=self.application_name)
        objects = objects.filter(upstream_application_name=upstream_application_name)
        objects = objects.filter(pipeline_id=pipeline_id)
        objects = objects.filter(notification_id=notification_id)
        return bool(objects.count())

    def all_sequence_ids(self) -> Iterable[UUID]:
        sequence_id_fieldname = self.field_names.sequence_id
        values_queryset = self.record_class.objects.values(  # type: ignore
            sequence_id_fieldname
        ).distinct()
        for values in values_queryset:
            yield values[sequence_id_fieldname]

    def get_field_kwargs(self, item: object) -> Dict[str, Any]:
        kwargs = super().get_field_kwargs(item)
        state_fieldname = self.field_names.state
        state = kwargs[state_fieldname]
        if isinstance(state, memoryview):
            state = bytes(state)
            kwargs[state_fieldname] = state
        return kwargs
