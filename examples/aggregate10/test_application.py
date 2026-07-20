from __future__ import annotations

from unittest import TestCase

from examples.aggregate10.application import DogSchool
from examples.aggregate10.domainmodel import Dog


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
        # self.assertIsInstance(dog["created_on"], datetime)
        # self.assertIsInstance(dog["modified_on"], datetime)

        # Select notifications.
        notifications = school.notification_log.select(start=1, limit=10)
        assert len(notifications) == 3

        # Take snapshot.
        school.take_snapshot(dog_id, Dog, version=3)
        dog = school.get_dog(dog_id)
        self.assertEqual(dog["name"], "Fido")
        self.assertEqual(dog["tricks"], ("roll over", "play dead"))
        # self.assertIsInstance(dog["created_on"], datetime)
        # self.assertIsInstance(dog["modified_on"], datetime)

        # Continue with snapshotted aggregate.
        school.add_trick(dog_id, "fetch ball")
        dog = school.get_dog(dog_id)
        self.assertEqual(dog["name"], "Fido")
        self.assertEqual(dog["tricks"], ("roll over", "play dead", "fetch ball"))
        # self.assertIsInstance(dog["created_on"], datetime)
        # self.assertIsInstance(dog["modified_on"], datetime)
