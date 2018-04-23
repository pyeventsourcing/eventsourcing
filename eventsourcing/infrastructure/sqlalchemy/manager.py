from functools import reduce

from sqlalchemy import asc, bindparam, desc, or_, select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound
from sqlalchemy.sql import func

from eventsourcing.exceptions import ProgrammingError
from eventsourcing.infrastructure.base import AbstractTrackingRecordManager, RelationalRecordManager
from eventsourcing.infrastructure.sqlalchemy.records import NotificationTrackingRecord
from eventsourcing.utils.uuids import uuid_from_application_name


class SQLAlchemyRecordManager(RelationalRecordManager):
    tracking_record_class = NotificationTrackingRecord

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
        if hasattr(record_class, 'application_id') and 'application_id' not in field_names:
            field_names.append('application_id')
        if hasattr(record_class, 'pipeline_id') and 'pipeline_id' not in field_names:
            field_names.append('pipeline_id')
        if hasattr(record_class, 'causal_dependencies') and 'causal_dependencies' not in field_names:
            field_names.append('causal_dependencies')
        if hasattr(record_class, 'id') and placeholder_for_id and 'id' not in field_names:
            field_names.append('id')

        statement = text(tmpl.format(
            tablename=self.get_record_table_name(record_class),
            columns=", ".join(field_names),
            placeholders=", ".join([":{}".format(f) for f in field_names]),
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

    def _write_records(self, records, tracking_kwargs=None):
        try:
            with self.session.bind.begin() as connection:
                if tracking_kwargs:
                    # Add tracking record to session.
                    params = {c: tracking_kwargs[c] for c in self.tracking_record_field_names}
                    connection.execute(self.insert_tracking_record, **params)

                for record in records:

                    params = {c: getattr(record, c) for c in self.field_names}
                    if hasattr(self.record_class, 'application_id'):
                        params['application_id'] = self.application_id
                    if hasattr(self.record_class, 'pipeline_id'):
                        params['pipeline_id'] = self.pipeline_id
                    if hasattr(record, 'causal_dependencies'):
                        params['causal_dependencies'] = record.causal_dependencies

                    statement = self.insert_values

                    if hasattr(self.record_class, 'id'):
                        if record.id is None and self.contiguous_record_ids:
                            statement = self.insert_select_max
                        else:
                            # Are record ID unique in table? Not if there are different applications.
                            if hasattr(self.record_class, 'application_id'):
                                # Record ID is not auto-incrementing.
                                assert record.id, "record ID not set when required"
                            params['id'] = record.id

                    connection.execute(statement, **params)

        except IntegrityError as e:
            self.raise_record_integrity_error(e)

        except OperationalError as e:
            self.raise_operational_error(e)

    def get_records(self, sequence_id, gt=None, gte=None, lt=None, lte=None, limit=None,
                    query_ascending=True, results_ascending=True):
        assert limit is None or limit >= 1, limit
        try:
            # Filter by sequence_id.
            filter_kwargs = {
                self.field_names.sequence_id: sequence_id
            }
            # Optionally, filter by application_id.
            if hasattr(self.record_class, 'application_id'):
                filter_kwargs['application_id'] = self.application_id
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
            if hasattr(self.record_class, 'application_id'):
                query = query.filter(self.record_class.application_id == self.application_id)
            if hasattr(self.record_class, 'pipeline_id'):
                query = query.filter(self.record_class.pipeline_id == self.pipeline_id)
            if hasattr(self.record_class, 'id'):
                query = query.order_by(asc('id'))
                # NB '+1' because record IDs start from 1.
                if start is not None:
                    query = query.filter(self.record_class.id >= start + 1)
                if stop is not None:
                    query = query.filter(self.record_class.id < stop + 1)
            # Todo: Should some tables with an ID not be ordered by ID?
            # Todo: Which order do other tables have?
            return query.all()
        finally:
            self.session.close()

    def get_item(self, sequence_id, position):
        return self.from_record(self.get_record(sequence_id, position))

    def get_pipeline_and_notification_id(self, sequence_id, position):
        # Todo: Optimise query by selecting only two columns: pipeline_id and id (notification ID).
        record = self.get_record(sequence_id, position)
        return record.pipeline_id, record.id

    def get_record(self, sequence_id, position):
        try:
            filter_args = {self.field_names.sequence_id: sequence_id}
            query = self.filter_by(**filter_args)
            position_field = getattr(self.record_class, self.field_names.position)
            query = query.filter(position_field == position)
            return query.one()
        except (NoResultFound, MultipleResultsFound):
            raise IndexError
        finally:
            self.session.close()

    def filter_by(self, **kwargs):
        return self.orm_query().filter_by(**kwargs)

    def orm_query(self):
        return self.session.query(self.record_class)

    def get_max_record_id(self):
        try:
            query = self.session.query(func.max(self.record_class.id))
            if hasattr(self.record_class, 'application_id'):
                query = query.filter(self.record_class.application_id == self.application_id)
            if hasattr(self.record_class, 'pipeline_id'):
                query = query.filter(self.record_class.pipeline_id == self.pipeline_id)

            return query.scalar()
        finally:
            self.session.close()

    def all_sequence_ids(self):
        c = self.record_class.__table__.c
        sequence_id_col = getattr(c, self.field_names.sequence_id)
        expr = select([sequence_id_col], distinct=True)

        if hasattr(self.record_class, 'application_id'):
            expr = expr.where(c.application_id == self.application_id)

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


class TrackingRecordManager(AbstractTrackingRecordManager):
    record_class = NotificationTrackingRecord

    def __init__(self, session):
        self.session = session

    def get_max_record_id(self, application_name, upstream_application_name, pipeline_id):
        application_id = uuid_from_application_name(application_name)
        upstream_application_id = uuid_from_application_name(upstream_application_name)
        query = self.session.query(func.max(self.record_class.notification_id))
        query = query.filter(self.record_class.application_id == application_id)
        query = query.filter(self.record_class.upstream_application_id == upstream_application_id)
        query = query.filter(self.record_class.pipeline_id == pipeline_id)
        return query.scalar()

    def has_tracking_record(self, application_id, upstream_application_name, pipeline_id, notification_id):
        upstream_application_id = uuid_from_application_name(upstream_application_name)
        query = self.session.query(self.record_class)
        query = query.filter(self.record_class.application_id == application_id)
        query = query.filter(self.record_class.upstream_application_id == upstream_application_id)
        query = query.filter(self.record_class.pipeline_id == pipeline_id)
        query = query.filter(self.record_class.notification_id == notification_id)
        try:
            query.one()
        except (MultipleResultsFound, NoResultFound):
            return False
        else:
            return True
