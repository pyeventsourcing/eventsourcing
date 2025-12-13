from __future__ import annotations

from typing import TYPE_CHECKING, Any

from examples.aggregate9.domainmodel import Trick, add_trick, project_dog, register_dog
from examples.aggregate9.immutablemodel import Snapshot
from examples.aggregate9.msgpack import MsgspecApplication

if TYPE_CHECKING:
    from uuid import UUID


class DogSchool(MsgspecApplication):
    is_snapshotting_enabled = True
    snapshot_class = Snapshot

    def register_dog(self, name: str) -> UUID:
        event = register_dog(name)
        self.save(event)
        return event.originator_id

    def add_trick(self, dog_id: UUID, trick: str) -> None:
        dog = self.repository.get(dog_id, projector_func=project_dog)
        self.save(add_trick(dog, Trick(name=trick)))

    def get_dog(self, dog_id: UUID) -> dict[str, Any]:
        dog = self.repository.get(dog_id, projector_func=project_dog)
        return {
            "id": dog.id,
            "name": dog.name,
            "tricks": tuple([t.name for t in dog.tricks]),
            "created_on": dog.created_on,
            "modified_on": dog.modified_on,
        }
