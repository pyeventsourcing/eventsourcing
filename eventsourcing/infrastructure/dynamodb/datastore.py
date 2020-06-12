from typing import Tuple, TypeVar

from pynamodb.exceptions import TableError
from pynamodb.models import Model

from eventsourcing.infrastructure.datastore import AbstractDatastore, \
    DatastoreSettings

TPynamoDbModel = TypeVar("TPynamoDbModel", bound=Model)


class DynamoDbSettings(DatastoreSettings):
    def __init__(self, wait_for_table=False):
        """
        :param wait_for_table: wait for table creation (default: False)
        """
        self.wait_for_table = wait_for_table


class DynamoDbDatastore(AbstractDatastore):
    def __init__(self, tables: Tuple[TPynamoDbModel], *args, **kwargs):
        super().__init__(*args, **kwargs)
        assert isinstance(tables, tuple), tables
        self.tables: Tuple[TPynamoDbModel] = tables or []

    def setup_connection(self):
        return

    def close_connection(self):
        return

    def setup_tables(self):
        for table in self.tables:
            self.setup_table(table)

    def setup_table(self, table: TPynamoDbModel) -> None:
        from pynamodb.models import Model
        try:
            issubclass(table, Model)
        except TypeError:
            raise ValueError("Models must be derived from base Model.")

        table.create_table(wait=self.settings.wait_for_table)

    def drop_tables(self) -> None:
        for table in self.tables:
            try:
                self.drop_table(table)
            except TableError:
                # skip if table not found
                continue

    def drop_table(self, table: Model) -> None:
        table.delete_table()

    def truncate_tables(self):
        """
        Truncate or drop tables

        This is used during unit test teardown here:
        eventsourcing.tests.sequenced_item_tests.base.WithRecordManagers
        """
        self.drop_tables()
