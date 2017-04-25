from tempfile import NamedTemporaryFile

from sqlalchemy.exc import OperationalError

from eventsourcing.infrastructure.datastore import DatastoreTableError
from eventsourcing.infrastructure.sqlalchemy.activerecords import SqlIntegerSequencedItem
from eventsourcing.infrastructure.sqlalchemy.datastore import Base, DEFAULT_SQLALCHEMY_DB_URI, SQLAlchemyDatastore, \
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
            base=Base,
            settings=SQLAlchemySettings(uri=uri),
        )


class TestSQLAlchemyDatastore(SQLAlchemyDatastoreTestCase, DatastoreTestCase):
    def list_records(self):
        try:
            query = self.datastore.db_session.query(SqlIntegerSequencedItem)
            return list(query)
        except OperationalError as e:
            self.datastore.db_session.rollback()
            raise DatastoreTableError(e)

    def create_record(self):
        try:
            record = SqlIntegerSequencedItem()
            self.datastore.db_session.add(record)
            self.datastore.db_session.commit()
        except OperationalError as e:
            self.datastore.db_session.rollback()
            raise DatastoreTableError(e)
        return record
