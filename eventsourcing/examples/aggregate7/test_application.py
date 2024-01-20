from __future__ import annotations

from typing import Tuple
from unittest import TestCase

from eventsourcing.examples.aggregate7.application import DogSchool
from eventsourcing.examples.aggregate7.domainmodel import Trick, project_dog


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
        self.assertEqualTricks(dog["tricks"], ("roll over", "play dead"))

        # Select notifications.
        notifications = school.notification_log.select(start=1, limit=10)
        assert len(notifications) == 3

        # Take snapshot.
        school.take_snapshot(dog_id, version=3, projector_func=project_dog)
        dog = school.get_dog(dog_id)
        self.assertEqual(dog["name"], "Fido")
        self.assertEqualTricks(dog["tricks"], ("roll over", "play dead"))

        # Continue with snapshotted aggregate.
        school.add_trick(dog_id, "fetch ball")
        dog = school.get_dog(dog_id)
        self.assertEqual(dog["name"], "Fido")
        self.assertEqualTricks(dog["tricks"], ("roll over", "play dead", "fetch ball"))

    def assertEqualTricks(
        self, actual: Tuple[Trick, ...], expected: Tuple[str, ...]
    ) -> None:
        self.assertEqual(len(actual), len(expected))
        for i, trick in enumerate(actual):
            self.assertIsInstance(trick, Trick)
            self.assertEqual(trick.name, expected[i])
