from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

from eventsourcing.application import Application
from eventsourcing.examples.aggregate6.domainmodel import (
    add_trick,
    project_dog,
    register_dog,
)

if TYPE_CHECKING:  # pragma: nocover
    from uuid import UUID


class DogSchool(Application):
    is_snapshotting_enabled = True

    def register_dog(self, name: str) -> UUID:
        event = register_dog(name)
        self.save(event)
        return event.originator_id

    def add_trick(self, dog_id: UUID, trick: str) -> None:
        dog = self.repository.get(dog_id, projector_func=project_dog)
        self.save(add_trick(dog, trick))

    def get_dog(self, dog_id: UUID) -> Dict[str, Any]:
        dog = self.repository.get(dog_id, projector_func=project_dog)
        return {"name": dog.name, "tricks": dog.tricks}
