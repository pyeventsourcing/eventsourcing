import uuid

from eventsourcing.domain.model.entity import EventSourcedEntity, eventsourcedproperty, EntityRepository
from eventsourcing.domain.model.events import publish, DomainEvent


class Example(EventSourcedEntity):
    """
    An example event sourced domain model entity.
    """
    class Created(EventSourcedEntity.Created):
        pass

    class AttributeChanged(EventSourcedEntity.AttributeChanged):
        pass

    class Discarded(EventSourcedEntity.Discarded):
        pass

    class Heartbeat(DomainEvent):
        pass

    def __init__(self, a, b, **kwargs):
        super(Example, self).__init__(**kwargs)
        self._a = a
        self._b = b
        self._count_heartbeats = 0

    @eventsourcedproperty
    def a(self):
        return self._a

    @eventsourcedproperty()
    def b(self):
        return self._b

    def beat_heart(self):
        self._assert_not_discarded()
        event = self.Heartbeat(entity_id=self._id, entity_version=self._version)
        self._apply(event)
        publish(event)

    def count_heartbeats(self):
        return self._count_heartbeats

    @classmethod
    def mutator(cls, entity=None, event=None):
        assert isinstance(event, DomainEvent), "Not a domain event: {}".format(event)
        event_type = type(event)
        if event_type == cls.Heartbeat:
            assert isinstance(entity, Example), entity
            entity._count_heartbeats += 1
            entity._increment_version()
            return entity
        else:
            return super(Example, cls).mutator(entity, event)


class Repository(EntityRepository):

    pass


def register_new_example(a, b):
    """
    Factory method for example entities.
    """
    entity_id = uuid.uuid4().hex
    event = Example.Created(entity_id=entity_id, a=a, b=b)
    entity = Example.mutator(event=event)
    publish(event=event)
    return entity
