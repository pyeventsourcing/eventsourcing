from __future__ import annotations

from typing import Any

from eventsourcing.dataclasses import AggregatesApplication
from examples.aggregate5.domainmodel import Dog


class DogSchool(AggregatesApplication):
    is_snapshotting_enabled = True

    def register_dog(self, name: str) -> str:
        dog, event = Dog.register(name)
        self.save(event)
        return dog.id

    def add_trick(self, dog_id: str, trick: str) -> None:
        dog = self.repository.get(dog_id, projector=Dog.projector)
        dog, event = dog.add_trick(trick)
        self.save(event)

    def get_dog(self, dog_id: str) -> dict[str, Any]:
        dog = self.repository.get(dog_id, projector=Dog.projector)
        return {"name": dog.name, "tricks": dog.tricks}
