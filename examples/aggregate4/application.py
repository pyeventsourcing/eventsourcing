from __future__ import annotations

from typing import TYPE_CHECKING, Any

from eventsourcing.application import Application
from eventsourcing.dataclasses.transcoder import DataclassTranscoder
from eventsourcing.persistence import Transcoder
from examples.aggregate4.baseclasses import DomainEvent
from examples.aggregate4.domainmodel import Dog

if TYPE_CHECKING:
    from uuid import UUID


class DogSchool(Application[DomainEvent]):
    is_snapshotting_enabled = True

    def construct_transcoder(self) -> Transcoder[DomainEvent]:
        return DataclassTranscoder()

    def register_dog(self, name: str) -> UUID:
        dog = Dog.register(name)
        self.save(dog)
        return dog.id

    def add_trick(self, dog_id: UUID, trick: str) -> None:
        dog: Dog = self.repository.get(dog_id, projector_func=Dog.project_events)
        dog.add_trick(trick)
        self.save(dog)

    def get_dog(self, dog_id: UUID) -> dict[str, Any]:
        dog: Dog = self.repository.get(dog_id, projector_func=Dog.project_events)
        return {
            "name": dog.name,
            "tricks": tuple(dog.tricks),
            "created_on": dog.created_on,
            "modified_on": dog.modified_on,
        }
