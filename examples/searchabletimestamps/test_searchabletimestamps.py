from __future__ import annotations

import os
from datetime import timedelta
from time import sleep
from typing import ClassVar
from unittest import TestCase

from eventsourcing.domain import datetime_now_with_tzinfo
from eventsourcing.tests.postgres_utils import drop_tables
from examples.cargoshipping.domainmodel import Location
from examples.searchabletimestamps.application import (
    CargoNotFoundError,
    SearchableTimestampsApplication,
)


class SearchableTimestampsTestCase(TestCase):
    env: ClassVar[dict[str, str]]

    def test(self) -> None:
        # Construct application.
        app = SearchableTimestampsApplication(env=self.env)
        timestamp0 = datetime_now_with_tzinfo()
        sleep(1e-5)

        # Book new cargo.
        tracking_id = app.book_new_cargo(
            origin=Location["NLRTM"],
            destination=Location["USDAL"],
            arrival_deadline=datetime_now_with_tzinfo() + timedelta(weeks=3),
        )
        timestamp1 = datetime_now_with_tzinfo()
        sleep(1e-5)

        # Change destination.
        app.change_destination(tracking_id, destination=Location["AUMEL"])
        timestamp2 = datetime_now_with_tzinfo()
        sleep(1e-5)

        # View the state of the cargo tracking at particular times.
        with self.assertRaises(CargoNotFoundError):
            app.get_cargo_at_timestamp(tracking_id, timestamp0)

        cargo_at_timestamp1 = app.get_cargo_at_timestamp(tracking_id, timestamp1)
        self.assertEqual(cargo_at_timestamp1.destination, Location["USDAL"])

        cargo_at_timestamp2 = app.get_cargo_at_timestamp(tracking_id, timestamp2)
        self.assertEqual(cargo_at_timestamp2.destination, Location["AUMEL"])


class WithSQLite(SearchableTimestampsTestCase):
    env: ClassVar[dict[str, str]] = {
        "PERSISTENCE_MODULE": "examples.searchabletimestamps.sqlite",
        "SQLITE_DBNAME": ":memory:",
    }


class WithPostgreSQL(SearchableTimestampsTestCase):
    env: ClassVar[dict[str, str]] = {
        "PERSISTENCE_MODULE": "examples.searchabletimestamps.postgres"
    }

    def setUp(self) -> None:
        drop_tables()
        super().setUp()
        os.environ["POSTGRES_DBNAME"] = "eventsourcing"
        os.environ["POSTGRES_HOST"] = "127.0.0.1"
        os.environ["POSTGRES_PORT"] = "5432"
        os.environ["POSTGRES_USER"] = "eventsourcing"
        os.environ["POSTGRES_PASSWORD"] = "eventsourcing"  # noqa: S105

    def tearDown(self) -> None:
        super().tearDown()
        drop_tables()


del SearchableTimestampsTestCase
