from tempfile import NamedTemporaryFile

from sqlalchemy.exc import OperationalError

from eventsourcing.infrastructure.datastore import DatastoreTableError
from eventsourcing.infrastructure.sqlalchemy.activerecords import IntegerSequencedItemRecord, TimestampSequencedItemRecord, \
    SnapshotRecord
from eventsourcing.infrastructure.sqlalchemy.datastore import ActiveRecord, DEFAULT_SQLALCHEMY_DB_URI, SQLAlchemyDatastore, \
    SQLAlchemySettings
from eventsourcing.tests.datastore_tests.base import AbstractDatastoreTestCase, DatastoreTestCase


class SQLAlchemyDatastoreTestCase(AbstractDatastoreTestCase):
    use_named_temporary_file = False

    def construct_datastore(self):
        if self.use_named_temporary_file:
            self.temp_file = NamedTemporaryFile('a', delete=True)
            uri = 'sqlite:///' + self.temp_file.name
        else:
            uri = DEFAULT_SQLALCHEMY_DB_URI
        return SQLAlchemyDatastore(
            base=ActiveRecord,
            settings=SQLAlchemySettings(uri=uri),
            tables=(IntegerSequencedItemRecord, TimestampSequencedItemRecord, SnapshotRecord),
        )


class TestSQLAlchemyDatastore(SQLAlchemyDatastoreTestCase, DatastoreTestCase):
    def list_records(self):
        try:
            query = self.datastore.db_session.query(IntegerSequencedItemRecord)
            return list(query)
        except OperationalError as e:
            self.datastore.db_session.rollback()
            raise DatastoreTableError(e)

    def create_record(self):
        try:
            record = IntegerSequencedItemRecord()
            self.datastore.db_session.add(record)
            self.datastore.db_session.commit()
        except OperationalError as e:
            self.datastore.db_session.rollback()
            raise DatastoreTableError(e)
        return record
