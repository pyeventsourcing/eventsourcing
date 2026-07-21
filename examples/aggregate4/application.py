from __future__ import annotations

from typing import Any

from eventsourcing.dataclasses import AggregatesApplication
from examples.aggregate4.domainmodel import Dog


class DogSchool(AggregatesApplication):
    is_snapshotting_enabled = True

    def register_dog(self, name: str) -> str:
        dog = Dog.register(name)
        self.save(dog)
        return dog.id

    def add_trick(self, dog_id: str, trick: str) -> None:
        dog: Dog = self.repository.get(dog_id, projector=Dog.project_events)
        dog.add_trick(trick)
        self.save(dog)

    def get_dog(self, dog_id: str) -> dict[str, Any]:
        dog = self.repository.get(dog_id, projector=Dog.project_events)
        assert dog is not None
        return {
            "name": dog.name,
            "tricks": tuple(dog.tricks),
            "created_on": dog.created_on,
            "modified_on": dog.modified_on,
        }
