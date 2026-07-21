from __future__ import annotations

from typing import Any

from eventsourcing.dataclasses import AggregatesApplication
from examples.aggregate6.domainmodel import (
    add_trick,
    mutate_dog,
    register_dog,
)


class DogSchool(AggregatesApplication):
    is_snapshotting_enabled = True

    def register_dog(self, name: str) -> str:
        event = register_dog(name)
        self.save(event)
        return event.originator_id

    def add_trick(self, dog_id: str, trick: str) -> None:
        dog = self.repository.get(dog_id, projector=mutate_dog)
        self.save(add_trick(dog, trick))

    def get_dog(self, dog_id: str) -> dict[str, Any]:
        dog = self.repository.get(dog_id, projector=mutate_dog)
        return {"name": dog.name, "tricks": dog.tricks}
