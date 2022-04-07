from typing import Any, Dict
from uuid import UUID

from eventsourcing.application import Application
from eventsourcing.examples.aggregate5.domainmodel import Dog


class DogSchool(Application):
    is_snapshotting_enabled = True

    def register_dog(self, name: str) -> UUID:
        dog, events = Dog.register(name)
        self.save(*events)
        return dog.id

    def add_trick(self, dog_id: UUID, trick: str) -> None:
        dog = self.repository.get(dog_id, projector_func=Dog.projector)
        dog, events = dog.add_trick(trick)
        self.save(*events)

    def get_dog(self, dog_id: UUID) -> Dict[str, Any]:
        dog = self.repository.get(dog_id, projector_func=Dog.projector)
        return {"name": dog.name, "tricks": dog.tricks}
