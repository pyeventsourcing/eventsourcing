from typing import Any, Dict, Iterable, List, Optional, Sequence, Union
from uuid import UUID

import sqlalchemy.exc
from sqlalchemy import asc, bindparam, desc, select, text
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound
from sqlalchemy.sql import func

from eventsourcing.exceptions import OperationalError, ProgrammingError
from eventsourcing.infrastructure.base import (
    BaseRecordManager,
    SQLRecordManager,
    TrackingKwargs,
)


class SQLAlchemyRecordManager(SQLRecordManager):
    _where_application_name_tmpl = (
        " WHERE application_name=:application_name AND pipeline_id=:pipeline_id"
    )

    def __init__(self, session: Any, *args: Any, **kwargs: Any):
        super(SQLAlchemyRecordManager, self).__init__(*args, **kwargs)
        self.session = session

    def _prepare_insert(
        self,
        tmpl: Any,
        record_class: type,
        field_names: List[str],
        placeholder_for_id: bool = False,
    ) -> Any:
        """
        With transaction isolation level of "read committed" this should
        generate records with a contiguous sequence of integer IDs, assumes
        an indexed ID column, the database-side SQL max function, the
        insert-select-from form, and optimistic concurrency control.
        """
        statement = super()._prepare_insert(
            tmpl, record_class, field_names, placeholder_for_id
        )
        statement = text(statement)

        # Define bind parameters with explicit types taken from record column types.
        bindparams = []
        for col_name in field_names:
            column_type = getattr(record_class, col_name).type
            bindparams.append(bindparam(col_name, type_=column_type))

        # Redefine statement with explicitly typed bind parameters.
        statement = statement.bindparams(*bindparams)

        return statement

    def make_placeholder(self, field_name: str) -> str:
        return ":{}".format(field_name)

    def write_records(
        self,
        records: Iterable[Any],
        tracking_kwargs: Optional[TrackingKwargs] = None,
        orm_objs_pending_save: Optional[Sequence[Any]] = None,
        orm_objs_pending_delete: Optional[Sequence[Any]] = None,
    ) -> None:

        all_params = []
        statement = None
        if not isinstance(records, list):
            records = list(records)
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

                    elif hasattr(self.record_class, "application_name"):
                        # Can't allow auto-incrementing ID if table has field
                        # application_name. We need values and don't have them.
                        raise ProgrammingError("record ID not set when required")

            for record in records:
                # Params for stored item itself (e.g. event).
                params = {name: getattr(record, name) for name in self.field_names}

                # Params for application partition (bounded context).
                if hasattr(self.record_class, "application_name"):
                    params["application_name"] = self.application_name

                # Params for notification log.
                if self.notification_id_name:
                    notification_id = getattr(record, self.notification_id_name)
                    if notification_id == "event-not-notifiable":
                        params[self.notification_id_name] = None
                    else:
                        params[self.notification_id_name] = notification_id

                    if hasattr(self.record_class, "pipeline_id"):
                        if notification_id == "event-not-notifiable":
                            params["pipeline_id"] = None
                        else:
                            params["pipeline_id"] = self.pipeline_id

                if hasattr(record, "causal_dependencies"):
                    params["causal_dependencies"] = record.causal_dependencies

                all_params.append(params)

        try:
            nothing_to_commit = True

            # Commit custom ORM objects.
            if orm_objs_pending_save:
                for orm_obj in orm_objs_pending_save:
                    self.session.add(orm_obj)
                nothing_to_commit = False

            if orm_objs_pending_delete:
                for orm_obj in orm_objs_pending_delete:
                    self.session.delete(orm_obj)
                nothing_to_commit = False

            # Insert tracking record.
            if tracking_kwargs:
                self.session.execute(self.insert_tracking_record, tracking_kwargs)
                nothing_to_commit = False

            # Bulk insert event records.
            if all_params:
                self.session.execute(statement, all_params)
                nothing_to_commit = False

            if nothing_to_commit:
                return

            self.session.commit()

        except sqlalchemy.exc.IntegrityError as e:
            self.session.rollback()
            self.raise_record_integrity_error(e)

        except sqlalchemy.exc.DBAPIError as e:
            self.session.rollback()
            self.raise_operational_error(e)

        except:
            self.session.rollback()
            raise

        finally:
            self.session.close()

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
        try:
            # Filter by sequence_id.
            filter_kwargs: Dict[str, Union[UUID, str]] = {
                self.field_names.sequence_id: sequence_id
            }
            # Optionally, filter by application_name.
            if hasattr(self.record_class, "application_name"):
                assert self.application_name
                filter_kwargs["application_name"] = self.application_name
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

            # Get the results.
            results = list(query.all())

        except sqlalchemy.exc.OperationalError as e:
            raise OperationalError(e)

        finally:
            self.session.close()

        # Reverse if necessary.
        if results_ascending != query_ascending:
            # This code path is under test, but not otherwise used ATM.
            results.reverse()

        return results

    def get_notification_records(
        self,
        start: Optional[int] = None,
        stop: Optional[int] = None,
        *args: Any,
        **kwargs: Any
    ) -> Iterable:
        try:
            query = self.orm_query()
            query = self.filter_for_application_name(query)
            query = self.filter_for_pipeline_id(query)

            if self.notification_id_name:
                query = query.order_by(asc(self.notification_id_name))
                # NB '+1' because record IDs start from 1.
                notification_id_col = getattr(
                    self.record_class, self.notification_id_name
                )
                if start is not None:
                    query = query.filter(notification_id_col >= start + 1)
                if stop is not None:
                    query = query.filter(notification_id_col < stop + 1)
            # Todo: Should some tables with an ID not be ordered by ID?
            # Todo: Which order do other tables have?
            return list(query.all())
        except sqlalchemy.exc.OperationalError as e:
            raise OperationalError(e)
        finally:
            self.session.close()

    def get_record(self, sequence_id: UUID, position: int) -> Any:
        """
        Gets record at position in sequence.
        """
        try:
            filter_args = {self.field_names.sequence_id: sequence_id}

            query = self.filter_by(**filter_args)

            query = self.filter_for_application_name(query)

            position_field = getattr(self.record_class, self.field_names.position)
            query = query.filter(position_field == position)
            return query.one()
        except (NoResultFound, MultipleResultsFound):
            raise IndexError(self.application_name, sequence_id, position)

    def filter_for_application_name(self, query: Any) -> Any:
        try:
            application_name_field = getattr(self.record_class, "application_name")
        except AttributeError:
            pass
        else:
            query = query.filter(application_name_field == self.application_name)
        return query

    def filter_for_pipeline_id(self, query: Any) -> Any:
        try:
            pipeline_id_field = getattr(self.record_class, "pipeline_id")
        except AttributeError:
            pass
        else:
            query = query.filter(pipeline_id_field == self.pipeline_id)
        return query

    def filter_by(self, **kwargs: Any) -> Any:
        return self.orm_query().filter_by(**kwargs)

    def orm_query(self) -> Any:
        return self.session.query(self.record_class)

    def get_max_notification_id(self) -> int:
        try:
            notification_id_col = getattr(self.record_class, self.notification_id_name)
            query = self.session.query(func.max(notification_id_col))
            query = self.filter_for_application_name(query)
            query = self.filter_for_pipeline_id(query)
            return query.scalar() or 0
        finally:
            self.session.close()

    def get_max_tracking_record_id(self, upstream_application_name: str) -> int:
        assert self.tracking_record_class is not None
        application_name_field = (
            self.tracking_record_class.application_name  # type: ignore
        )
        upstream_app_name_field = (
            self.tracking_record_class.upstream_application_name  # type: ignore
        )
        pipeline_id_field = self.tracking_record_class.pipeline_id  # type: ignore
        notification_id_field = (
            self.tracking_record_class.notification_id  # type: ignore
        )
        query = self.session.query(func.max(notification_id_field))
        query = query.filter(application_name_field == self.application_name)
        query = query.filter(upstream_app_name_field == upstream_application_name)
        query = query.filter(pipeline_id_field == self.pipeline_id)
        value = query.scalar() or 0
        return value

    def has_tracking_record(
        self, upstream_application_name: str, pipeline_id: int, notification_id: int
    ) -> bool:
        query = self.session.query(self.tracking_record_class)
        application_name_field = (
            self.tracking_record_class.application_name  # type: ignore
        )
        upstream_name_field = (
            self.tracking_record_class.upstream_application_name  # type: ignore
        )
        pipeline_id_field = self.tracking_record_class.pipeline_id  # type: ignore
        notification_id_field = (
            self.tracking_record_class.notification_id  # type: ignore
        )

        query = query.filter(application_name_field == self.application_name)
        query = query.filter(upstream_name_field == upstream_application_name)
        query = query.filter(pipeline_id_field == pipeline_id)
        query = query.filter(notification_id_field == notification_id)
        try:
            query.one()
        except (MultipleResultsFound, NoResultFound):
            return False
        else:
            return True

    def all_sequence_ids(self) -> Iterable[UUID]:
        c = self.record_class.__table__.c  # type: ignore
        sequence_id_col = getattr(c, self.field_names.sequence_id)
        expr = select([sequence_id_col], distinct=True)

        if hasattr(self.record_class, "application_name"):
            expr = expr.where(c.application_name == self.application_name)

        try:
            for row in self.session.query(expr):
                yield row[0]
        finally:
            self.session.close()

    def delete_record(self, record: Any) -> None:
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

    def get_record_table_name(self, record_class: type) -> str:
        return record_class.__table__.name  # type: ignore

    def clone(
        self, application_name: str, pipeline_id: int, **kwargs: Any
    ) -> BaseRecordManager:
        return super().clone(
            application_name=application_name,
            pipeline_id=pipeline_id,
            session=self.session,
            **kwargs
        )
