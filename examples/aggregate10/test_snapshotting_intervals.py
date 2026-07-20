from __future__ import annotations

from typing import Any, ClassVar
from unittest import TestCase

from examples.aggregate10.application import DogSchool
from examples.aggregate10.domainmodel import Dog


class SubDogSchool(DogSchool):
    snapshotting_intervals: ClassVar[dict[type[Any], int]] = {Dog: 1}


class TestDogSchool(TestCase):
    def test_dog_school(self) -> None:
        # Construct application object.
        school = SubDogSchool()

        # Evolve application state.
        dog_id = school.register_dog("Fido")
        assert school.snapshots is not None
        self.assertEqual(1, len(list(school.snapshots.get(dog_id))))

        school.add_trick(dog_id, "roll over")
        self.assertEqual(2, len(list(school.snapshots.get(dog_id))))

        school.add_trick(dog_id, "play dead")
        self.assertEqual(3, len(list(school.snapshots.get(dog_id))))

        # Query application state.
        dog = school.get_dog(dog_id)
        self.assertEqual(dog["name"], "Fido")
        self.assertEqual(dog["tricks"], ("roll over", "play dead"))
