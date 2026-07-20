from __future__ import annotations

from unittest import TestCase

from eventsourcing.domain_new import put_metadata_in_context
from examples.aggregate6.application import DogSchool


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
        assert dog["name"] == "Fido"
        assert dog["tricks"] == ("roll over", "play dead")

        # Select notifications.
        notifications = school.notification_log.select(start=1, limit=10)
        assert len(notifications) == 3

        # # Take snapshot.
        # with put_metadata_in_context({"user_id": "admin-1"}):
        #     school.take_snapshot(dog_id, version=3, projector=project_dog)
        # dog = school.get_dog(dog_id)
        # assert dog["name"] == "Fido"
        # assert dog["tricks"] == ("roll over", "play dead")
        #
        # # Continue with snapshotted aggregate.
        # with put_metadata_in_context({"user_id": "user-1"}):
        #     school.add_trick(dog_id, "fetch ball")
        # dog = school.get_dog(dog_id)
        # assert dog["name"] == "Fido"
        # assert dog["tricks"] == ("roll over", "play dead", "fetch ball")
        #

        # Check metadata on events.
        events = list(school.events.get(dog_id))
        assert len(events) > 0
        for event in events:
            assert event.metadata.get("user_id") == "user-1"
        #
        # # Check metadata on snapshots.
        # assert school.snapshots is not None
        # snapshots = list(school.snapshots.get(dog_id))
        # assert len(snapshots) > 0
        # for snapshot in snapshots:
        #     assert snapshot.metadata.get("user_id") == "admin-1"
