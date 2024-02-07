from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Dict, Type

from eventsourcing.application import Application, ProjectorFunction
from eventsourcing.examples.aggregate7.persistence import (
    OrjsonTranscoder,
    PydanticMapper,
)
from eventsourcing.examples.aggregate7a.domainmodel import (
    Dog,
    Snapshot,
    add_trick,
    project_dog,
    register_dog,
)

if TYPE_CHECKING:  # pragma: nocover
    from uuid import UUID

    from eventsourcing.domain import MutableOrImmutableAggregate
    from eventsourcing.persistence import Mapper, Transcoder


class DogSchool(Application):
    is_snapshotting_enabled = True
    snapshot_class = Snapshot
    snapshotting_intervals: ClassVar[
        Dict[Type[MutableOrImmutableAggregate], int] | None
    ] = {Dog: 5}
    snapshotting_projectors: ClassVar[
        Dict[Type[MutableOrImmutableAggregate], ProjectorFunction[Any, Any]] | None
    ] = {Dog: project_dog}

    def register_dog(self, name: str) -> UUID:
        dog = register_dog(name)
        self.save(dog)
        return dog.id

    def add_trick(self, dog_id: UUID, trick: str) -> None:
        dog = self.repository.get(dog_id, projector_func=project_dog)
        dog = add_trick(dog, trick)
        self.save(dog)

    def get_dog(self, dog_id: UUID) -> Dict[str, Any]:
        dog = self.repository.get(dog_id, projector_func=project_dog)
        return {"name": dog.name, "tricks": tuple([t.name for t in dog.tricks])}

    def construct_mapper(self) -> Mapper:
        return self.factory.mapper(
            transcoder=self.construct_transcoder(),
            mapper_class=PydanticMapper,
        )

    def construct_transcoder(self) -> Transcoder:
        return OrjsonTranscoder()
