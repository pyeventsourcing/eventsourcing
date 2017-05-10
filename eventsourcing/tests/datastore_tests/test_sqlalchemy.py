from tempfile import NamedTemporaryFile
from uuid import uuid4

from sqlalchemy.exc import OperationalError
# from sqlalchemy.pool import StaticPool

from eventsourcing.infrastructure.datastore import DatastoreTableError
from eventsourcing.infrastructure.sqlalchemy.activerecords import IntegerSequencedItemRecord, TimestampSequencedItemRecord, \
    SnapshotRecord
from eventsourcing.infrastructure.sqlalchemy.datastore import ActiveRecord, DEFAULT_SQLALCHEMY_DB_URI, SQLAlchemyDatastore, \
    SQLAlchemySettings
from eventsourcing.tests.datastore_tests.base import AbstractDatastoreTestCase, DatastoreTestCase


class SQLAlchemyDatastoreTestCase(AbstractDatastoreTestCase):
    use_named_temporary_file = False
    connection_strategy = 'plain'

    def construct_datastore(self):
        if self.use_named_temporary_file:
            self.temp_file = NamedTemporaryFile('a', delete=True)
            uri = 'sqlite:///' + self.temp_file.name
        else:
            uri = DEFAULT_SQLALCHEMY_DB_URI

        # kwargs = {}
        # if not self.use_named_temporary_file:
            # kwargs['connect_args'] = {'check_same_thread':False}
            # kwargs['poolclass'] = StaticPool

        return SQLAlchemyDatastore(
            base=ActiveRecord,
            settings=SQLAlchemySettings(uri=uri),
            tables=(IntegerSequencedItemRecord, TimestampSequencedItemRecord, SnapshotRecord),
            connection_strategy=self.connection_strategy,
            # **kwargs
        )


class TestSQLAlchemyDatastore(SQLAlchemyDatastoreTestCase, DatastoreTestCase):
    def list_records(self):
        try:
            query = self.datastore.session.query(IntegerSequencedItemRecord)
            return list(query)
        except OperationalError as e:
            self.datastore.session.rollback()
            raise DatastoreTableError(e)

    def create_record(self):
        try:
            record = IntegerSequencedItemRecord(sequence_id=uuid4(), position=0)
            self.datastore.session.add(record)
            self.datastore.session.commit()
        except OperationalError as e:
            self.datastore.session.rollback()
            raise DatastoreTableError(e)
        return record
