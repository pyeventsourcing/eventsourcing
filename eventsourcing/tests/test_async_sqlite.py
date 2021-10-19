from eventsourcing.sqlite import (
    SQLiteAggregateRecorder,
    SQLiteApplicationRecorder,
    SQLiteDatastore,
    SQLiteProcessRecorder,
)
from eventsourcing.tests.async_aggregaterecorder_testcase import (
    AsyncAggregateRecorderTestCase,
)
from eventsourcing.tests.async_applicationrecorder_testcase import (
    AsyncApplicationRecorderTestCase,
)
from eventsourcing.tests.async_processrecorder_testcase import (
    AsyncProcessRecorderTestCase,
)
from eventsourcing.tests.ramdisk import tmpfile_uris


class TestSQLiteAggregateRecorder(AsyncAggregateRecorderTestCase):
    async def create_recorder(self):
        recorder = SQLiteAggregateRecorder(SQLiteDatastore(self.db_uri))
        recorder.create_table()
        return recorder

    async def test_insert_and_select(self):
        self.db_uri = ":memory:"
        await super().test_insert_and_select()

    async def test_insert_and_select_file_db(self):
        self.uris = tmpfile_uris()
        self.db_uri = next(self.uris)
        await super().test_insert_and_select()

    async def test_performance(self):
        self.db_uri = ":memory:"
        await super().test_performance()

    async def test_performance_concurrent(self):
        self.db_uri = ":memory:"
        await super().test_performance_concurrent()

    async def test_performance_file_db(self):
        self.uris = tmpfile_uris()
        self.db_uri = next(self.uris)
        await super().test_performance()


class TestSQLiteApplicationRecorder(AsyncApplicationRecorderTestCase):
    async def create_recorder(self):
        recorder = SQLiteApplicationRecorder(SQLiteDatastore(self.db_uri))
        recorder.create_table()
        return recorder

    async def test_insert_select(self):
        self.uris = tmpfile_uris()
        self.db_uri = next(self.uris)
        await super().test_insert_select()

    async def test_insert_select_in_memory_db(self):
        self.db_uri = ":memory:"
        await super().test_insert_select()

    def test_concurrent_no_conflicts(self):
        self.uris = tmpfile_uris()
        self.db_uri = next(self.uris)
        super().test_concurrent_no_conflicts()

    def test_concurrent_no_conflicts_in_memory_db(self):
        self.db_uri = "file::memory:?cache=shared"
        super().test_concurrent_no_conflicts()

    def test_concurrent_throughput(self):
        self.uris = tmpfile_uris()
        self.db_uri = next(self.uris)
        super().test_concurrent_throughput()

    def test_concurrent_throughput_in_memory_db(self):
        self.db_uri = "file::memory:?cache=shared"
        super().test_concurrent_throughput()


class TestSQLiteProcessRecorder(AsyncProcessRecorderTestCase):
    async def create_recorder(self):
        recorder = SQLiteProcessRecorder(SQLiteDatastore(self.db_uri))
        recorder.create_table()
        return recorder

    async def test_insert_select(self):
        self.db_uri = ":memory:"
        await super().test_insert_select()

    async def test_insert_select_file_db(self):
        self.uris = tmpfile_uris()
        self.db_uri = next(self.uris)
        await super().test_insert_select()

    async def test_performance(self):
        self.db_uri = ":memory:"
        await super().test_performance()

    async def test_performance_file_db(self):
        self.uris = tmpfile_uris()
        self.db_uri = next(self.uris)
        await super().test_performance()


del AsyncAggregateRecorderTestCase
del AsyncApplicationRecorderTestCase
del AsyncProcessRecorderTestCase
