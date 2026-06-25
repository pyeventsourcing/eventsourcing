from __future__ import annotations

from typing import Any

from eventsourcing.pydantic.application import PydanticApplication
from eventsourcing.pydantic.immutablemodel import Snapshot
from examples.aggregate7_str_ids.domainmodel import (
    Trick,
    add_trick,
    project_dog,
    register_dog,
)


class DogSchool(PydanticApplication[str]):
    is_snapshotting_enabled = True
    snapshot_class = Snapshot[str]

    def register_dog(self, name: str) -> str:
        event = register_dog(name)
        self.save(event)
        return event.originator_id

    def add_trick(self, dog_id: str, trick: str) -> None:
        dog = self.repository.get(dog_id, projector_func=project_dog)
        self.save(add_trick(dog, Trick(name=trick)))

    def get_dog(self, dog_id: str) -> dict[str, Any]:
        dog = self.repository.get(dog_id, projector_func=project_dog)
        return {
            "name": dog.name,
            "tricks": tuple([t.name for t in dog.tricks]),
            "created_on": dog.created_on,
            "modified_on": dog.modified_on,
        }
