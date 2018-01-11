import six
from sqlalchemy import asc, desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from sqlalchemy.sql.expression import func

from eventsourcing.exceptions import ProgrammingError
from eventsourcing.infrastructure.base import RelationalRecordManager


class SQLAlchemyRecordManager(RelationalRecordManager):
    def __init__(self, session, *args, **kwargs):
        super(SQLAlchemyRecordManager, self).__init__(*args, **kwargs)
        self.session = session

    def _write_records(self, records, sequenced_items):
        try:
            # Todo: Do this on the database-side...
            # record_id = None
            # if self.contiguous_record_ids:
            #     sel = self.session.query(func.max(self.record_class.id)).scalar()
            #     record_id = 0 if sel is None else sel

            # Add record(s) to the transaction.
            for record in records:

                # Todo: Do this on the database-side,
                # so that the time between checking and
                # using the value is as short as possible.
                # if self.contiguous_record_ids:
                #     record_id += 1
                #     record.id = record_id

                self.session.add(record)

            self.session.commit()
        except IntegrityError as e:
            self.session.rollback()
            # raise
            self.raise_sequenced_item_error(sequenced_items)
        finally:
            self.session.close()

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

        # try:
        #     return events[0]
        # except IndexError:
        #     self.raise_index_error(eq)

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

    def all_records(self, *args, **kwargs):
        """
        Returns all records in the table.
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
            return self.query.all()
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
