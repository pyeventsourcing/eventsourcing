from typing import Any, Dict
from uuid import UUID

from eventsourcing.application import Application
from eventsourcing.examples.alternative_aggregate7.domainmodel import (
    add_trick,
    project_dog,
    register_dog,
)
from eventsourcing.examples.alternative_aggregate7.persistence import (
    OrjsonTranscoder,
    PydanticMapper,
)
from eventsourcing.persistence import Mapper, Transcoder


class DogSchool(Application):
    is_snapshotting_enabled = True

    def register_dog(self, name: str) -> UUID:
        dog, events = register_dog(name)
        self.save(*events)
        return dog.id

    def add_trick(self, dog_id: UUID, trick: str) -> None:
        dog = self.repository.get(dog_id, projector_func=project_dog)
        dog, events = add_trick(dog, trick)
        self.save(*events)

    def get_dog(self, dog_id: UUID) -> Dict[str, Any]:
        dog = self.repository.get(dog_id, projector_func=project_dog)
        return {"name": dog.name, "tricks": dog.tricks}

    def construct_mapper(self) -> Mapper:
        return self.factory.mapper(
            transcoder=self.construct_transcoder(),
            mapper_class=PydanticMapper,
        )

    def construct_transcoder(self) -> Transcoder:
        return OrjsonTranscoder()
