import os

from eventsourcing.persistence import InfrastructureFactory
from eventsourcing.sqlite import (
    SQLiteAggregateRecorder,
    SQLiteApplicationRecorder,
    SQLiteDatastore,
    Factory,
    SQLiteProcessRecorder,
)
from eventsourcing.tests.aggregaterecorder_testcase import (
    AggregateRecorderTestCase,
)
from eventsourcing.tests.applicationrecorder_testcase import (
    ApplicationRecorderTestCase,
)
from eventsourcing.tests.infrastructure_testcases import (
    InfrastructureFactoryTestCase,
)
from eventsourcing.tests.processrecorder_testcase import ProcessRecordsTestCase
from eventsourcing.tests.ramdisk import tmpfile_uris
from eventsourcing.utils import get_topic


class TestSQLiteAggregateRecorder(AggregateRecorderTestCase):
    def create_recorder(self):
        recorder = SQLiteAggregateRecorder(SQLiteDatastore(":memory:"))
        recorder.create_table()
        return recorder


class TestSQLiteApplicationRecorder(ApplicationRecorderTestCase):
    def test_insert_select(self):
        self.db_uri = ":memory:"
        super().test_insert_select()

    def test_concurrent_no_conflicts(self):
        # db_uri = "file::memory:?cache=shared"
        self.uris = tmpfile_uris()
        self.db_uri = next(self.uris)
        super().test_insert_select()

    def create_recorder(self):
        recorder = SQLiteApplicationRecorder(SQLiteDatastore(self.db_uri))
        recorder.create_table()
        return recorder


class TestSQLiteProcessRecorder(ProcessRecordsTestCase):
    def create_recorder(self):
        recorder = SQLiteProcessRecorder(SQLiteDatastore(":memory:"))
        recorder.create_table()
        return recorder


class TestSQLiteInfrastructureFactory(InfrastructureFactoryTestCase):
    def setUp(self) -> None:
        os.environ[InfrastructureFactory.TOPIC] = get_topic(Factory)
        os.environ[Factory.SQLITE_DBNAME] = ":memory:"
        super().setUp()

    def tearDown(self) -> None:
        super().tearDown()
        del os.environ[Factory.SQLITE_DBNAME]


del AggregateRecorderTestCase
del ApplicationRecorderTestCase
del ProcessRecordsTestCase
del InfrastructureFactoryTestCase
