from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

from eventsourcing.application import Application
from eventsourcing.examples.aggregate8.domainmodel import Dog, Trick
from eventsourcing.examples.aggregate8.persistence import (
    OrjsonTranscoder,
    PydanticMapper,
)

if TYPE_CHECKING:  # pragma: nocover
    from uuid import UUID

    from eventsourcing.persistence import Mapper, Transcoder


class DogSchool(Application):
    is_snapshotting_enabled = True

    def register_dog(self, name: str) -> UUID:
        dog = Dog(name)
        self.save(dog)
        return dog.id

    def add_trick(self, dog_id: UUID, trick: str) -> None:
        dog: Dog = self.repository.get(dog_id)
        dog.add_trick(Trick(name=trick))
        self.save(dog)

    def get_dog(self, dog_id: UUID) -> Dict[str, Any]:
        dog: Dog = self.repository.get(dog_id)
        return {
            "name": dog.name,
            "tricks": tuple([t.name for t in dog.tricks]),
            "created_on": dog.created_on,
            "modified_on": dog.modified_on,
        }

    def construct_mapper(self) -> Mapper:
        return self.factory.mapper(
            transcoder=self.construct_transcoder(),
            mapper_class=PydanticMapper,
        )

    def construct_transcoder(self) -> Transcoder:
        return OrjsonTranscoder()
