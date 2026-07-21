from __future__ import annotations

from typing import Any

from eventsourcing.pydantic.application import PydanticAggregatesApplication
from examples.aggregate8.domainmodel import Dog, Trick


class DogSchool(PydanticAggregatesApplication):
    is_snapshotting_enabled = True

    def register_dog(self, name: str) -> str:
        dog = Dog(name)
        self.save(dog)
        return dog.id

    def add_trick(self, dog_id: str, trick: str) -> None:
        dog = self.repository.get(dog_id, Dog)
        dog.add_trick(Trick(name=trick))
        self.save(dog)

    def get_dog(self, dog_id: str) -> dict[str, Any]:
        dog = self.repository.get(dog_id, Dog)
        return {
            "name": dog.name,
            "tricks": tuple([t.name for t in dog.tricks]),
        }
