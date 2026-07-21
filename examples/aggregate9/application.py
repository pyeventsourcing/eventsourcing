from __future__ import annotations

from typing import Any

from eventsourcing.msgspec import AggregatesApplication
from examples.aggregate9.domainmodel import (
    Trick,
    add_trick,
    evolve_dog,
    register_dog,
)


class DogSchool(AggregatesApplication):
    is_snapshotting_enabled = True

    def register_dog(self, name: str) -> str:
        event = register_dog(name)
        self.save(event)
        return event.originator_id

    def add_trick(self, dog_id: str, trick: str) -> None:
        dog = self.repository.get(dog_id, projector=evolve_dog)
        self.save(add_trick(dog, Trick(name=trick)))

    def get_dog(self, dog_id: str) -> dict[str, Any]:
        dog = self.repository.get(dog_id, projector=evolve_dog)
        return {
            "id": dog.id,
            "name": dog.name,
            "tricks": tuple([t.name for t in dog.tricks]),
        }
