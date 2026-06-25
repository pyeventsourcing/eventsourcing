from __future__ import annotations

from datetime import datetime
from unittest import TestCase

from eventsourcing.domain import put_metadata_in_context
from examples.aggregate7_str_ids.application import DogSchool
from examples.aggregate7_str_ids.domainmodel import project_dog


class TestDogSchool(TestCase):
    def test_dog_school(self) -> None:
        # Construct application object.
        school = DogSchool()

        # Evolve application state.
        with put_metadata_in_context({"user_id": "user-1"}):
            dog_id = school.register_dog("Fido")
            school.add_trick(dog_id, "roll over")
            school.add_trick(dog_id, "play dead")

        # Query application state.
        dog = school.get_dog(dog_id)
        self.assertEqual(dog["name"], "Fido")
        self.assertEqual(dog["tricks"], ("roll over", "play dead"))
        self.assertIsInstance(dog["created_on"], datetime)
        self.assertIsInstance(dog["modified_on"], datetime)

        # Select notifications.
        notifications = school.notification_log.select(start=1, limit=10)
        assert len(notifications) == 3

        # Take snapshot.
        with put_metadata_in_context({"user_id": "admin-1"}):
            school.take_snapshot(dog_id, version=3, projector_func=project_dog)
        dog = school.get_dog(dog_id)
        self.assertEqual(dog["name"], "Fido")
        self.assertEqual(dog["tricks"], ("roll over", "play dead"))
        self.assertIsInstance(dog["created_on"], datetime)
        self.assertIsInstance(dog["modified_on"], datetime)

        # Continue with snapshotted aggregate.
        with put_metadata_in_context({"user_id": "user-1"}):
            school.add_trick(dog_id, "fetch ball")
        dog = school.get_dog(dog_id)
        self.assertEqual(dog["name"], "Fido")
        self.assertEqual(dog["tricks"], ("roll over", "play dead", "fetch ball"))
        self.assertIsInstance(dog["created_on"], datetime)
        self.assertIsInstance(dog["modified_on"], datetime)

        # Check metadata on events.
        events = list(school.events.get(dog_id))
        assert len(events) > 0
        for event in events:
            assert event.metadata.get("user_id") == "user-1"

        # Check metadata on snapshots.
        assert school.snapshots is not None
        snapshots = list(school.snapshots.get(dog_id))
        assert len(snapshots) > 0
        for snapshot in snapshots:
            assert snapshot.metadata.get("user_id") == "admin-1"
