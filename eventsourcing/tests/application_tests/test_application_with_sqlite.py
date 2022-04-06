import os
from unittest import TestCase

from eventsourcing.tests.application import (
    TIMEIT_FACTOR,
    ApplicationTestCase,
    ExampleApplicationTestCase,
)
from eventsourcing.tests.persistence import tmpfile_uris


class WithSQLiteFile(TestCase):
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


class WithSQLiteInMemory(TestCase):
    timeit_number = 30 * TIMEIT_FACTOR
    expected_factory_topic = "eventsourcing.sqlite:Factory"

    def setUp(self) -> None:
        super().setUp()
        os.environ["PERSISTENCE_MODULE"] = "eventsourcing.sqlite"
        os.environ["CREATE_TABLE"] = "y"
        os.environ["SQLITE_DBNAME"] = "file:memory:?mode=memory&cache=shared"

    def tearDown(self) -> None:
        del os.environ["PERSISTENCE_MODULE"]
        del os.environ["CREATE_TABLE"]
        del os.environ["SQLITE_DBNAME"]
        super().tearDown()


class TestApplicationWithSQLiteFile(ApplicationTestCase, WithSQLiteFile):
    pass


# class TestApplicationWithSQLiteInMemory(TestApplication, WithSQLiteInMemory):
#     pass


class TestExampleApplicationWithSQLiteFile(ExampleApplicationTestCase, WithSQLiteFile):
    timeit_number = 30 * TIMEIT_FACTOR
    expected_factory_topic = "eventsourcing.sqlite:Factory"


class TestExampleApplicationWithSQLiteInMemory(
    ExampleApplicationTestCase, WithSQLiteInMemory
):
    timeit_number = 30 * TIMEIT_FACTOR
    expected_factory_topic = "eventsourcing.sqlite:Factory"


del ApplicationTestCase
del ExampleApplicationTestCase
del WithSQLiteFile
del WithSQLiteInMemory
