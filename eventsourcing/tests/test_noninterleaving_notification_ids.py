from eventsourcing.persistence import ApplicationRecorder
from eventsourcing.popo import POPOApplicationRecorder
from eventsourcing.postgres import (
    PostgresApplicationRecorder,
    PostgresDatastore,
)
from eventsourcing.sqlite import SQLiteApplicationRecorder, SQLiteDatastore
from eventsourcing.tests.noninterleaving_notification_ids_testcase import (
    NonInterleavingNotificationIDsBaseCase,
)
from eventsourcing.tests.ramdisk import tmpfile_uris
from eventsourcing.tests.test_postgres import drop_postgres_table


class TestNonInterleavingPOPO(NonInterleavingNotificationIDsBaseCase):
    insert_num = 10000

    def create_recorder(self) -> ApplicationRecorder:
        return POPOApplicationRecorder()


class TestNonInterleavingSQLiteInMemory(NonInterleavingNotificationIDsBaseCase):
    insert_num = 10000

    def create_recorder(self) -> ApplicationRecorder:
        recorder = SQLiteApplicationRecorder(
            SQLiteDatastore(db_name="file::memory:?cache=shared")
        )
        recorder.create_table()
        return recorder


class TestNonInterleavingSQLiteFileDB(NonInterleavingNotificationIDsBaseCase):
    insert_num = 10000

    def create_recorder(self) -> ApplicationRecorder:
        self.uris = tmpfile_uris()
        self.db_uri = next(self.uris)

        recorder = SQLiteApplicationRecorder(SQLiteDatastore(db_name=self.db_uri))
        recorder.create_table()
        return recorder


class TestNonInterleavingPostgres(NonInterleavingNotificationIDsBaseCase):
    insert_num = 100

    def setUp(self) -> None:
        self.datastore = PostgresDatastore(
            "eventsourcing",
            "127.0.0.1",
            "5432",
            "eventsourcing",
            "eventsourcing",
        )
        self.drop_table()

    def tearDown(self) -> None:
        self.drop_table()

    def drop_table(self):
        drop_postgres_table(self.datastore, "stored_events")

    def create_recorder(self) -> ApplicationRecorder:
        self.uris = tmpfile_uris()
        self.db_uri = next(self.uris)
        recorder = PostgresApplicationRecorder(self.datastore)
        recorder.create_table()
        return recorder


del NonInterleavingNotificationIDsBaseCase
