from typing import Any, Dict
from uuid import UUID

from eventsourcing.application import Application
from eventsourcing.examples.alternative_aggregate6.domainmodel import (
    add_trick,
    project_dog,
    register_dog,
)


class DogSchool(Application):
    is_snapshotting_enabled = True

    def register_dog(self, name: str) -> UUID:
        dog, events = register_dog(name)
        self.save(*events)  # type: ignore
        return dog.id

    def add_trick(self, dog_id: UUID, trick: str) -> None:
        dog = self.repository.get(dog_id, projector_func=project_dog)
        dog, events = add_trick(dog, trick)
        self.save(*events)  # type: ignore

    def get_dog(self, dog_id: UUID) -> Dict[str, Any]:
        dog = self.repository.get(dog_id, projector_func=project_dog)
        return {"name": dog.name, "tricks": tuple(dog.tricks)}
