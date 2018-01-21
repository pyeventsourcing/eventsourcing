import six
from sqlalchemy import asc, bindparam, desc, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound
from sqlalchemy.sql import func

from eventsourcing.exceptions import ProgrammingError
from eventsourcing.infrastructure.base import RelationalRecordManager


class SQLAlchemyRecordManager(RelationalRecordManager):
    def __init__(self, session, *args, **kwargs):
        super(SQLAlchemyRecordManager, self).__init__(*args, **kwargs)
        self.session = session

    def _write_records(self, records):
        try:
            if self.contiguous_record_ids:
                for record in records:
                    # Execute "insert select max" statement with values from record obj.
                    params = {c: getattr(record, c) for c in self.field_names}
                    self.session.bind.execute(self.insert_select_max, **params)
            else:
                for record in records:
                    # Execute "insert values" statement with values from record obj.
                    params = {c: getattr(record, c) for c in self.field_names}
                    self.session.bind.execute(self.insert_values, **params)

                    # Old way:
                    # # Add record obj to session.
                    # self.session.add(record)

            self.session.commit()
        except IntegrityError as e:
            self.session.rollback()

            self.raise_after_integrity_error(e)

        finally:
            self.session.close()

    @property
    def record_table_name(self):
        return self.record_class.__table__.name

    def _prepare_insert(self, tmpl):
        """
        With transaction isolation level of "read committed" this should
        generate records with a contiguous sequence of integer IDs, assumes
        an indexed ID column, the database-side SQL max function, the
        insert-select-from form, and optimistic concurrency control.
        """
        statement = text(tmpl.format(
            tablename=self.record_table_name,
            columns=", ".join(self.field_names),
            placeholders=", ".join([":{}".format(f) for f in self.field_names]),
        ))

        # Define bind parameters with explicit types taken from record column types.
        bindparams = []
        for col_name in self.field_names:
            column_type = getattr(self.record_class, col_name).type
            bindparams.append(bindparam(col_name, type_=column_type))

        # Redefine statement with explicitly typed bind parameters.
        statement = statement.bindparams(*bindparams)

        # Compile the statement with the session dialect.
        compiled = statement.compile(dialect=self.session.bind.dialect)

        return compiled

    def get_item(self, sequence_id, eq):
        try:
            filter_args = {self.field_names.sequence_id: sequence_id}
            query = self.filter(**filter_args)
            position_field = getattr(self.record_class, self.field_names.position)
            query = query.filter(position_field == eq)
            result = query.one()
        except (NoResultFound, MultipleResultsFound):
            raise IndexError
        finally:
            self.session.close()
        return self.from_record(result)

    def get_items(self, sequence_id, gt=None, gte=None, lt=None, lte=None, limit=None,
                  query_ascending=True, results_ascending=True):
        records = self.get_records(
            sequence_id=sequence_id,
            gt=gt,
            gte=gte,
            lt=lt,
            lte=lte,
            limit=limit,
            query_ascending=query_ascending,
            results_ascending=results_ascending,

        )
        for item in six.moves.map(self.from_record, records):
            yield item

    def get_records(self, sequence_id, gt=None, gte=None, lt=None, lte=None, limit=None,
                    query_ascending=True, results_ascending=True):
        assert limit is None or limit >= 1, limit
        try:
            filter_kwargs = {self.field_names.sequence_id: sequence_id}
            query = self.filter(**filter_kwargs)

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

            if limit is not None:
                query = query.limit(limit)

            results = query.all()

        finally:
            self.session.close()

        if results_ascending != query_ascending:
            # This code path is under test, but not otherwise used ATM.
            results.reverse()

        return results

    def filter(self, **kwargs):
        return self.query.filter_by(**kwargs)

    @property
    def query(self):
        return self.session.query(self.record_class)

    def all_items(self):
        """
        Returns all items across all sequences.
        """
        return six.moves.map(self.from_record, self.all_records())

    def all_records(self, start=None, stop=None, *args, **kwargs):
        """
        Returns all records in the table.

        Intended to support getting all application domain events
        in order, especially if the records have contiguous IDs.
        """
        # query = self.filter(**kwargs)
        # if resume is not None:
        #     query = query.offset(resume + 1)
        # else:
        #     resume = 0
        # query = query.limit(100)
        # for i, record in enumerate(query):
        #     yield record, i + resume
        try:
            query = self.query
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

    def get_max_record_id(self):
        return self.session.query(func.max(self.record_class.id)).scalar()

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
