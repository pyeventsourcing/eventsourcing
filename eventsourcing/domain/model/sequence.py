from eventsourcing.domain.model.entity import EventSourcedEntity, EntityRepository
from eventsourcing.domain.model.events import DomainEvent, publish


class Sequence(EventSourcedEntity):
    class Started(EventSourcedEntity.Created):
        """Occurs when sequence is started."""

    class Appended(DomainEvent):
        """Occurs when item is appended."""

    @property
    def name(self):
        return self.id


def start_sequence(name):
    event = Sequence.Started(entity_id=name)
    entity = Sequence.mutate(event=event)
    publish(event)
    return entity


class SequenceRepository(EntityRepository):
    pass
