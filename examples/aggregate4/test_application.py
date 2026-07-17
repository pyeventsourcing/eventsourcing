from __future__ import annotations

from unittest import TestCase

from eventsourcing.domain_new import put_metadata_in_context
from examples.aggregate4.application import DogSchool
from examples.aggregate4.domainmodel import Dog


class TestDogSchool(TestCase):
    def test_dog_school(self) -> None:
        # Construct application object.
        school = DogSchool()

        # Evolve application state.
        with put_metadata_in_context({"user_id": "user-1"}):
            dog_id = school.register_dog("Fido")

        # Query application state.
        dog = school.get_dog(dog_id)
        assert dog["name"] == "Fido"
        assert dog["tricks"] == ()
        assert dog["created_on"] == dog["modified_on"]

        # Evolve application state.
        with put_metadata_in_context({"user_id": "user-1"}):
            school.add_trick(dog_id, "roll over")
            school.add_trick(dog_id, "play dead")

        # Query application state.
        dog = school.get_dog(dog_id)
        assert dog["name"] == "Fido"
        assert dog["tricks"] == ("roll over", "play dead")
        assert dog["created_on"] < dog["modified_on"]

        # Select notifications.
        notifications = school.notification_log.select(start=1, limit=10)
        assert len(notifications) == 3

        # Take snapshot.
        with put_metadata_in_context({"user_id": "admin-1"}):
            school.take_snapshot(dog_id, version=3, projector_func=Dog.project_events)

        # Continue with snapshotted aggregate.
        dog = school.get_dog(dog_id)
        assert dog["name"] == "Fido"
        assert dog["tricks"] == ("roll over", "play dead")
        assert dog["created_on"] < dog["modified_on"]

        with put_metadata_in_context({"user_id": "user-1"}):
            school.add_trick(dog_id, "fetch ball")

        dog = school.get_dog(dog_id)
        assert dog["name"] == "Fido"
        assert dog["tricks"] == ("roll over", "play dead", "fetch ball")
        assert dog["created_on"] < dog["modified_on"]

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
