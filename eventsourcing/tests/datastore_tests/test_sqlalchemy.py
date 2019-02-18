from tempfile import NamedTemporaryFile
from uuid import uuid4

from sqlalchemy.exc import OperationalError, ProgrammingError

from eventsourcing.infrastructure.datastore import DatastoreTableError
from eventsourcing.infrastructure.sqlalchemy.datastore import DEFAULT_SQLALCHEMY_DB_URI, SQLAlchemyDatastore, \
    SQLAlchemySettings
from eventsourcing.infrastructure.sqlalchemy.factory import SQLAlchemyInfrastructureFactory
from eventsourcing.infrastructure.sqlalchemy.records import Base, IntegerSequencedNoIDRecord, \
    IntegerSequencedWithIDRecord, SnapshotRecord, TimestampSequencedNoIDRecord, TimestampSequencedWithIDRecord
from eventsourcing.tests.datastore_tests import base


class SQLAlchemyDatastoreTestCase(base.AbstractDatastoreTestCase):
    """
    Base class for test cases that use an SQLAlchemy datastore.
    """

    use_named_temporary_file = False
    connection_strategy = 'plain'
    infrastructure_factory_class = SQLAlchemyInfrastructureFactory
    contiguous_record_ids = True

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
            base=Base,
            settings=SQLAlchemySettings(uri=uri),
            tables=(
                IntegerSequencedWithIDRecord,
                IntegerSequencedNoIDRecord,
                TimestampSequencedWithIDRecord,
                TimestampSequencedNoIDRecord,
                SnapshotRecord
            ),
            connection_strategy=self.connection_strategy,
            # **kwargs
        )


class TestSQLAlchemyDatastore(SQLAlchemyDatastoreTestCase, base.DatastoreTestCase):
    """
    Test case for SQLAlchemy datastore.
    """
    def list_records(self):
        try:
            query = self.datastore.session.query(IntegerSequencedNoIDRecord)
            return list(query)
        except (OperationalError, ProgrammingError) as e:
            # OperationalError from sqlite, ProgrammingError from psycopg2.
            self.datastore.session.rollback()
            raise DatastoreTableError(e)
        finally:
            self.datastore.session.close()

    def create_record(self):
        try:
            record = IntegerSequencedNoIDRecord(
                sequence_id=uuid4(),
                position=0,
                topic='topic',
                state='{}'
            )
            self.datastore.session.add(record)
            self.datastore.session.commit()
        except (OperationalError, ProgrammingError) as e:
            self.datastore.session.rollback()
            raise DatastoreTableError(e)
        return record
