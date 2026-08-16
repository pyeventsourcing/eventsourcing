import os
from abc import ABC
from collections.abc import Iterator
from typing import override
from unittest import TestCase

from eventsourcing.tests.application import (
    ApplicationTestCase,
    ExampleApplicationTestCase,
)
from eventsourcing.tests.persistence import tmpfile_uris


class WithSQLite(TestCase, ABC):
    expected_factory_topic = "eventsourcing.sqlite:SQLiteFactory"
    uris: Iterator[str] = iter(())

    @override
    def setUp(self) -> None:
        super().setUp()
        os.environ["PERSISTENCE_MODULE"] = "eventsourcing.sqlite"
        os.environ["CREATE_TABLE"] = "y"
        os.environ["SQLITE_DBNAME"] = next(self.uris)

    @override
    def tearDown(self) -> None:
        del os.environ["PERSISTENCE_MODULE"]
        del os.environ["CREATE_TABLE"]
        del os.environ["SQLITE_DBNAME"]
        super().tearDown()


class WithSQLiteFile(WithSQLite):
    uris = tmpfile_uris()


def memory_uris() -> Iterator[str]:
    db_number = 1
    while True:
        uri = f"file:db{db_number}?mode=memory&cache=shared"
        yield uri
        db_number += 1


class WithSQLiteInMemory(WithSQLite):
    uris = memory_uris()


class TestApplicationWithSQLiteFile(WithSQLiteFile, ApplicationTestCase):
    def test_catchup_subscription(self) -> None:
        self.skipTest("SQLite recorder doesn't support subscriptions")

    @override
    def test_application_with_cached_aggregates_and_fastforward(self) -> None:
        super().test_application_with_cached_aggregates_and_fastforward()


class TestApplicationWithSQLiteInMemory(WithSQLiteInMemory, ApplicationTestCase):
    def test_catchup_subscription(self) -> None:
        self.skipTest("SQLite recorder doesn't support subscriptions")


class TestExampleApplicationWithSQLiteFile(WithSQLiteFile, ExampleApplicationTestCase):
    pass


class TestExampleApplicationWithSQLiteInMemory(
    WithSQLiteInMemory, ExampleApplicationTestCase
):
    pass


del ApplicationTestCase
del ExampleApplicationTestCase
del WithSQLiteFile
del WithSQLiteInMemory
