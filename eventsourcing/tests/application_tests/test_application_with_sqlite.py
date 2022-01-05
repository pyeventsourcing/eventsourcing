import os

from eventsourcing.tests.application_tests.test_application_with_popo import (
    TIMEIT_FACTOR,
    TestApplicationWithPOPO,
)
from eventsourcing.tests.ramdisk import tmpfile_uris


class TestApplicationWithSQLiteFile(TestApplicationWithPOPO):
    timeit_number = 30 * TIMEIT_FACTOR
    expected_factory_topic = "eventsourcing.sqlite:Factory"

    def setUp(self) -> None:
        super().setUp()
        self.uris = tmpfile_uris()
        # self.db_uri = next(self.uris)

        os.environ["PERSISTENCE_MODULE"] = "eventsourcing.sqlite"
        os.environ["CREATE_TABLE"] = "y"
        os.environ["SQLITE_DBNAME"] = next(self.uris)

    def tearDown(self) -> None:
        del os.environ["PERSISTENCE_MODULE"]
        del os.environ["CREATE_TABLE"]
        del os.environ["SQLITE_DBNAME"]
        super().tearDown()


class TestApplicationWithSQLiteInMemory(TestApplicationWithPOPO):
    timeit_number = 30 * TIMEIT_FACTOR
    expected_factory_topic = "eventsourcing.sqlite:Factory"

    def setUp(self) -> None:
        super().setUp()
        os.environ["PERSISTENCE_MODULE"] = "eventsourcing.sqlite"
        os.environ["CREATE_TABLE"] = "y"
        os.environ["SQLITE_DBNAME"] = ":memory:"

    def tearDown(self) -> None:
        del os.environ["PERSISTENCE_MODULE"]
        del os.environ["CREATE_TABLE"]
        del os.environ["SQLITE_DBNAME"]
        super().tearDown()

    def test_example_application(self):
        super().test_example_application()


del TestApplicationWithPOPO
