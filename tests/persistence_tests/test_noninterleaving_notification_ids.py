from typing import override

from eventsourcing.persistence import ApplicationRecorder
from eventsourcing.popo import POPOApplicationRecorder
from eventsourcing.postgres import PostgresApplicationRecorder, PostgresDatastore
from eventsourcing.sqlite import SQLiteApplicationRecorder, SQLiteDatastore
from eventsourcing.tests.persistence import (
    NonInterleavingNotificationIDsBaseCase,
    tmpfile_uris,
)
from eventsourcing.tests.postgres_utils import drop_tables


class TestNonInterleavingPOPO(NonInterleavingNotificationIDsBaseCase):
    insert_num = 10000

    @override
    def create_recorder(self) -> ApplicationRecorder:
        return POPOApplicationRecorder()


class TestNonInterleavingSQLiteInMemory(NonInterleavingNotificationIDsBaseCase):
    insert_num = 10000

    @override
    def create_recorder(self) -> ApplicationRecorder:
        recorder = SQLiteApplicationRecorder(
            SQLiteDatastore(db_name="file::memory:?cache=shared")
        )
        recorder.create_table()
        return recorder


class TestNonInterleavingSQLiteFileDB(NonInterleavingNotificationIDsBaseCase):
    insert_num = 10000

    @override
    def create_recorder(self) -> ApplicationRecorder:
        self.uris = tmpfile_uris()
        self.db_uri = next(self.uris)

        recorder = SQLiteApplicationRecorder(SQLiteDatastore(db_name=self.db_uri))
        recorder.create_table()
        return recorder


class TestNonInterleavingPostgres(NonInterleavingNotificationIDsBaseCase):
    insert_num = 100

    @override
    def setUp(self) -> None:
        drop_tables()
        self.datastore = PostgresDatastore(
            "eventsourcing",
            "127.0.0.1",
            "5432",
            "eventsourcing",
            "eventsourcing",
        )

    @override
    def tearDown(self) -> None:
        self.datastore.close()
        drop_tables()

    @override
    def create_recorder(self) -> ApplicationRecorder:
        self.uris = tmpfile_uris()
        self.db_uri = next(self.uris)
        recorder = PostgresApplicationRecorder(self.datastore)
        recorder.create_table()
        return recorder


del NonInterleavingNotificationIDsBaseCase
