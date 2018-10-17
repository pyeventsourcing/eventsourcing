from sqlalchemy import asc, bindparam, desc, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound
from sqlalchemy.sql import func

from eventsourcing.exceptions import ProgrammingError
from eventsourcing.infrastructure.base import SQLRecordManager
from eventsourcing.infrastructure.sqlalchemy.records import NotificationTrackingRecord


class SQLAlchemyRecordManager(SQLRecordManager):
    tracking_record_class = NotificationTrackingRecord

    _where_application_name_tmpl = (
        " WHERE application_name=:application_name AND pipeline_id=:pipeline_id"
    )

    def __init__(self, session, *args, **kwargs):
        super(SQLAlchemyRecordManager, self).__init__(*args, **kwargs)
        self.session = session

    def _prepare_insert(self, tmpl, record_class, field_names, placeholder_for_id=False):
        """
        With transaction isolation level of "read committed" this should
        generate records with a contiguous sequence of integer IDs, assumes
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
        if self.notification_id_name:
            if placeholder_for_id:
                if self.notification_id_name not in field_names:
                    field_names.append(self.notification_id_name)

        statement = text(tmpl.format(
            tablename=self.get_record_table_name(record_class),
            columns=", ".join(field_names),
            placeholders=", ".join([":{}".format(f) for f in field_names]),
            notification_id=self.notification_id_name
        ))

        # Define bind parameters with explicit types taken from record column types.
        bindparams = []
        for col_name in field_names:
            column_type = getattr(record_class, col_name).type
            bindparams.append(bindparam(col_name, type_=column_type))

        # Redefine statement with explicitly typed bind parameters.
        statement = statement.bindparams(*bindparams)

        # Compile the statement with the session dialect.
        compiled = statement.compile(dialect=self.session.bind.dialect)

        return compiled

    def write_records(self, records, tracking_kwargs=None):
        all_params = []
        statement = None
        if records:
            # Prepare to insert event and notification records.
            statement = self.insert_values
            if self.notification_id_name:
                all_ids = set((getattr(r, self.notification_id_name) for r in records))
                if None in all_ids:
                    if len(all_ids) > 1:
                        # Either all or zero records must have IDs.
                        raise ProgrammingError("Only some records have IDs")

                    elif self.contiguous_record_ids:
                        # Do an "insert select max" from existing.
                        statement = self.insert_select_max

                    elif hasattr(self.record_class, 'application_name'):
                        # Can't allow auto-incrementing ID if table has field
                        # application_name. We need values and don't have them.
                        raise ProgrammingError("record ID not set when required")

            for record in records:
                # Params for stored item itself (e.g. event).
                params = {
                    name: getattr(record, name) for name in self.field_names
                }

                # Params for application partition (bounded context).
                if hasattr(self.record_class, 'application_name'):
                    params['application_name'] = self.application_name

                # Params for notification log.
                if self.notification_id_name:
                    notification_id = getattr(record, self.notification_id_name)
                    if notification_id == 'event-not-notifiable':
                        params[self.notification_id_name] = None
                    else:
                        params[self.notification_id_name] = notification_id

                    if hasattr(self.record_class, 'pipeline_id'):
                        if notification_id == 'event-not-notifiable':
                            params['pipeline_id'] = None
                        else:
                            params['pipeline_id'] = self.pipeline_id

                if hasattr(record, 'causal_dependencies'):
                    params['causal_dependencies'] = record.causal_dependencies

                all_params.append(params)

        elif not tracking_kwargs:
            # Don't bother if there is nothing to write.
            return

        try:

            with self.session.bind.begin() as connection:
                if tracking_kwargs:
                    # Insert tracking record.
                    connection.execute(self.insert_tracking_record, **tracking_kwargs)

                if all_params:
                    # Bulk insert event records.
                    connection.execute(statement, all_params)

        except IntegrityError as e:
            self.raise_record_integrity_error(e)

        except DBAPIError as e:
            self.raise_operational_error(e)

    def get_records(self, sequence_id, gt=None, gte=None, lt=None, lte=None, limit=None,
                    query_ascending=True, results_ascending=True):
        assert limit is None or limit >= 1, limit
        try:
            # Filter by sequence_id.
            filter_kwargs = {
                self.field_names.sequence_id: sequence_id
            }
            # Optionally, filter by application_name.
            if hasattr(self.record_class, 'application_name'):
                filter_kwargs['application_name'] = self.application_name
            query = self.filter_by(**filter_kwargs)

            # Filter and order by position.
            position_field = getattr(self.record_class, self.field_names.position)

            if query_ascending:
                query = query.order_by(asc(position_field))
            else:
                query = query.order_by(desc(position_field))

            if gt is not None:
                query = query.filter(position_field > gt)
            if gte is not None:
                query = query.filter(position_field >= gte)
            if lt is not None:
                query = query.filter(position_field < lt)
            if lte is not None:
                query = query.filter(position_field <= lte)

            # Limit the results.
            if limit is not None:
                query = query.limit(limit)

            # Get the result set.
            results = query.all()

        finally:
            self.session.close()

        # Reverse if necessary.
        if results_ascending != query_ascending:
            # This code path is under test, but not otherwise used ATM.
            results.reverse()

        return results

    def get_notifications(self, start=None, stop=None, *args, **kwargs):
        try:
            query = self.orm_query()
            if hasattr(self.record_class, 'application_name'):
                query = query.filter(self.record_class.application_name == self.application_name)
            if hasattr(self.record_class, 'pipeline_id'):
                query = query.filter(self.record_class.pipeline_id == self.pipeline_id)
            if self.notification_id_name:
                query = query.order_by(asc(self.notification_id_name))
                # NB '+1' because record IDs start from 1.
                notification_id_col = getattr(self.record_class, self.notification_id_name)
                if start is not None:
                    query = query.filter(notification_id_col >= start + 1)
                if stop is not None:
                    query = query.filter(notification_id_col < stop + 1)
            # Todo: Should some tables with an ID not be ordered by ID?
            # Todo: Which order do other tables have?
            return query.all()
        finally:
            self.session.close()

    def get_record(self, sequence_id, position):
        try:
            filter_args = {
                self.field_names.sequence_id: sequence_id
            }

            query = self.filter_by(**filter_args)
            if hasattr(self.record_class, 'application_name'):
                query = query.filter(
                    self.record_class.application_name == self.application_name
                )

            position_field = getattr(self.record_class, self.field_names.position)

            query = query.filter(position_field == position)
            return query.one()
        except (NoResultFound, MultipleResultsFound):
            raise IndexError(self.application_name, sequence_id, position)

    def filter_by(self, **kwargs):
        return self.orm_query().filter_by(**kwargs)

    def orm_query(self):
        return self.session.query(self.record_class)

    def get_max_record_id(self):
        try:
            notification_id_col = getattr(self.record_class, self.notification_id_name)
            query = self.session.query(func.max(notification_id_col))
            if hasattr(self.record_class, 'application_name'):
                query = query.filter(self.record_class.application_name == self.application_name)
            if hasattr(self.record_class, 'pipeline_id'):
                query = query.filter(self.record_class.pipeline_id == self.pipeline_id)

            return query.scalar()
        finally:
            self.session.close()

    def get_max_tracking_record_id(self, upstream_application_name):
        query = self.session.query(func.max(self.tracking_record_class.notification_id))
        query = query.filter(self.tracking_record_class.application_name == self.application_name)
        query = query.filter(self.tracking_record_class.upstream_application_name == upstream_application_name)
        query = query.filter(self.tracking_record_class.pipeline_id == self.pipeline_id)
        return query.scalar()

    def has_tracking_record(self, upstream_application_name, pipeline_id, notification_id):
        query = self.session.query(self.tracking_record_class)
        query = query.filter(self.tracking_record_class.application_name == self.application_name)
        query = query.filter(self.tracking_record_class.upstream_application_name == upstream_application_name)
        query = query.filter(self.tracking_record_class.pipeline_id == pipeline_id)
        query = query.filter(self.tracking_record_class.notification_id == notification_id)
        try:
            query.one()
        except (MultipleResultsFound, NoResultFound):
            return False
        else:
            return True

    def all_sequence_ids(self):
        c = self.record_class.__table__.c
        sequence_id_col = getattr(c, self.field_names.sequence_id)
        expr = select([sequence_id_col], distinct=True)

        if hasattr(self.record_class, 'application_name'):
            expr = expr.where(c.application_name == self.application_name)

        try:
            for row in self.session.query(expr):
                yield row[0]
        finally:
            self.session.close()

    def delete_record(self, record):
        """
        Permanently removes record from table.
        """
        try:
            self.session.delete(record)
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            raise ProgrammingError(e)
        finally:
            self.session.close()

    def get_record_table_name(self, record_class):
        return record_class.__table__.name

    def clone(self, **kwargs):
        return super(SQLAlchemyRecordManager, self).clone(session=self.session, **kwargs)
