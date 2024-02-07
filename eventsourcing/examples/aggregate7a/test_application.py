from __future__ import annotations

from unittest import TestCase

from eventsourcing.examples.aggregate7a.application import DogSchool
from eventsourcing.examples.aggregate7a.domainmodel import project_dog


class TestDogSchool(TestCase):
    def test_dog_school(self) -> None:
        # Construct application object.
        school = DogSchool()

        # Evolve application state.
        dog_id = school.register_dog("Fido")
        school.add_trick(dog_id, "roll over")
        school.add_trick(dog_id, "play dead")

        # Query application state.
        dog = school.get_dog(dog_id)
        self.assertEqual(dog["name"], "Fido")
        self.assertEqual(dog["tricks"], ("roll over", "play dead"))

        # Select notifications.
        notifications = school.notification_log.select(start=1, limit=10)
        assert len(notifications) == 3

        # Take snapshot.
        assert school.snapshots is not None
        assert len(list(school.snapshots.get(dog_id))) == 0
        school.take_snapshot(dog_id, version=3, projector_func=project_dog)
        assert len(list(school.snapshots.get(dog_id))) == 1
        dog = school.get_dog(dog_id)
        self.assertEqual(dog["name"], "Fido")
        self.assertEqual(dog["tricks"], ("roll over", "play dead"))

        # Continue with snapshotted aggregate.
        school.add_trick(dog_id, "fetch ball")
        dog = school.get_dog(dog_id)
        self.assertEqual(dog["name"], "Fido")
        self.assertEqual(dog["tricks"], ("roll over", "play dead", "fetch ball"))

        # Auto-snapshotting at version 5.
        assert len(list(school.snapshots.get(dog_id))) == 1
        school.add_trick(dog_id, "jump hoop")
        assert len(list(school.snapshots.get(dog_id))) == 2
