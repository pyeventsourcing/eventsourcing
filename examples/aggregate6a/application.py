from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from eventsourcing.application import Application, ProjectorFunction
from eventsourcing.domain import Snapshot
from examples.aggregate6a.domainmodel import Dog, add_trick, project_dog, register_dog

if TYPE_CHECKING:
    from uuid import UUID

    from eventsourcing.domain import MutableOrImmutableAggregate


class DogSchool(Application):
    is_snapshotting_enabled = True
    snapshotting_intervals: ClassVar[dict[type[MutableOrImmutableAggregate], int]] = {
        Dog: 5
    }
    snapshotting_projectors: ClassVar[
        dict[type[MutableOrImmutableAggregate], ProjectorFunction[Any, Any]]
    ] = {Dog: project_dog}
    snapshot_class = Snapshot

    def register_dog(self, name: str) -> UUID:
        dog = register_dog(name)
        self.save(dog)
        return dog.id

    def add_trick(self, dog_id: UUID, trick: str) -> None:
        dog = self.repository.get(dog_id, projector_func=project_dog)
        dog = add_trick(dog, trick)
        self.save(dog)

    def get_dog(self, dog_id: UUID) -> dict[str, Any]:
        dog = self.repository.get(dog_id, projector_func=project_dog)
        return {"name": dog.name, "tricks": dog.tricks}
