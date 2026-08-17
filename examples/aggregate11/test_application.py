from __future__ import annotations

import contextlib
import sys
from typing import override
from unittest import TestCase, skipIf

from examples.aggregate11.application import DogSchool

with contextlib.suppress(ImportError):
    # pyrefly: ignore [missing-import]
    import eventsourcing_kurrentdb  # noqa: F401  # pyright: ignore[reportMissingImports]


class TestDogSchool(TestCase):
    @override
    def setUp(self) -> None:
        self.env: dict[str, str] = {}

    def test_dog_school(self) -> None:
        # Construct application object.
        school = DogSchool(env=self.env)

        max_notification_id = school.recorder.max_notification_id()

        # Evolve application state.
        dog_id = school.register_dog("Fido")
        school.add_trick(dog_id, "roll over")
        school.add_trick(dog_id, "play dead")

        # Query application state.
        dog = school.get_dog(dog_id)
        self.assertEqual("Fido", dog["name"])
        self.assertEqual(("roll over", "play dead"), dog["tricks"])

        # Select notifications.
        notifications = school.notification_log.select(
            start=max_notification_id, limit=10, inclusive_of_start=False
        )
        self.assertEqual(3, len(notifications))

        # # Take snapshot.
        # school.take_snapshot(dog_id, Dog, version=3)
        # dog = school.get_dog(dog_id)
        # self.assertEqual("Fido", dog["name"])
        # self.assertEqual(("roll over", "play dead"), dog["tricks"])
        #
        # # Continue with snapshotted aggregate.
        # school.add_trick(dog_id, "fetch ball")
        # dog = school.get_dog(dog_id)
        # self.assertEqual("Fido", dog["name"])
        # self.assertEqual(("roll over", "play dead", "fetch ball"), dog["tricks"])

    def test_dog_school_with_sqlite(self) -> None:
        self.env["PERSISTENCE_MODULE"] = "eventsourcing.sqlite"
        self.env["SQLITE_DBNAME"] = ":memory:"
        self.env["ORIGINATOR_ID_TYPE"] = "text"
        self.test_dog_school()

    def test_dog_school_with_postgres(self) -> None:
        self.env["PERSISTENCE_MODULE"] = "eventsourcing.postgres"
        self.env["POSTGRES_DBNAME"] = "eventsourcing"
        self.env["POSTGRES_HOST"] = "127.0.0.1"
        self.env["POSTGRES_USER"] = "eventsourcing"
        self.env["POSTGRES_PASSWORD"] = "eventsourcing"  # noqa: S105
        self.env["ORIGINATOR_ID_TYPE"] = "text"
        self.test_dog_school()

    @skipIf("eventsourcing_kurrentdb" not in sys.modules, "KurrentDB not installed")
    def test_dog_school_with_kurrentdb(self) -> None:
        self.env["PERSISTENCE_MODULE"] = "eventsourcing_kurrentdb"
        self.env["KURRENTDB_URI"] = "esdb://localhost:2113?Tls=false"
        self.test_dog_school()
