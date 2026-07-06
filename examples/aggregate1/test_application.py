from __future__ import annotations

from unittest import TestCase

from examples.aggregate1.application import DogSchool
from examples.aggregate1.domainmodel import Dog


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
        self.assertEqual("Fido", dog["name"])
        self.assertEqual(("roll over", "play dead"), dog["tricks"])

        # Select notifications.
        notifications = school.notification_log.select(start=1, limit=10)
        self.assertEqual(3, len(notifications))

        # Take snapshot.
        school.take_snapshot(dog_id, Dog, version=3)
        dog = school.get_dog(dog_id)
        self.assertEqual("Fido", dog["name"])
        self.assertEqual(("roll over", "play dead"), dog["tricks"])

        # Continue with snapshotted aggregate.
        school.add_trick(dog_id, "fetch ball")
        dog = school.get_dog(dog_id)
        self.assertEqual("Fido", dog["name"])
        self.assertEqual(("roll over", "play dead", "fetch ball"), dog["tricks"])
