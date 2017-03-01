from sqlalchemy.exc import OperationalError

from eventsourcing.infrastructure.datastore.base import DatastoreTableError
from eventsourcing.infrastructure.datastore.sqlalchemy import SQLAlchemyDatastoreStrategy, SQLAlchemySettings
from eventsourcing.infrastructure.stored_event_repos.with_sqlalchemy import SqlStoredEvent
from eventsourcing.tests.datastore_tests.base import DatastoreStrategyTestCase


class TestSQLAlchemyDatastoreStrategy(DatastoreStrategyTestCase):

    def setup_datastore_strategy(self):
        # Setup the strategy.
        self.strategy = SQLAlchemyDatastoreStrategy(
            settings=SQLAlchemySettings(),
            tables=(SqlStoredEvent,),
        )

        # Todo: Encapsulate the driver exception classes.
    def list_records(self):
        try:
            query = self.strategy.db_session.query(SqlStoredEvent)
            return list(query)
        except OperationalError as e:
            self.strategy.db_session.rollback()
            raise DatastoreTableError(e)

    def create_record(self):
        try:
            record = SqlStoredEvent()
            self.strategy.db_session.add(record)
            self.strategy.db_session.commit()
        except OperationalError as e:
            self.strategy.db_session.rollback()
            raise DatastoreTableError(e)
        return record
