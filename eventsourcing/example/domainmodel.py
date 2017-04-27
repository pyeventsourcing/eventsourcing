import uuid

from eventsourcing.domain.model.entity import AbstractEntityRepository, TimestampedVersionedEntity, attribute, \
    mutate_entity
from eventsourcing.domain.model.events import mutator, publish


class Example(TimestampedVersionedEntity):
    """
    An example event sourced domain model entity.
    """

    class Event(TimestampedVersionedEntity.Event):
        """Layer supertype."""

    class Created(Event, TimestampedVersionedEntity.Created):
        """Published when an Example is created."""

    class AttributeChanged(Event, TimestampedVersionedEntity.AttributeChanged):
        """Published when an Example is created."""

    class Discarded(Event, TimestampedVersionedEntity.Discarded):
        """Published when an Example is discarded."""

    class Heartbeat(Event, TimestampedVersionedEntity.Event):
        """Published when a heartbeat in the entity occurs (see below)."""

    def __init__(self, foo='', a='', b='', **kwargs):
        super(Example, self).__init__(**kwargs)
        self._foo = foo
        self._a = a
        self._b = b
        self._count_heartbeats = 0

    @attribute
    def foo(self):
        """An example attribute."""

    @attribute
    def a(self):
        """An example attribute."""

    @attribute
    def b(self):
        """Another example attribute."""

    def beat_heart(self, number_of_beats=1):
        self._assert_not_discarded()
        events = []
        while number_of_beats > 0:
            event = self.Heartbeat(originator_id=self._id, originator_version=self._version)
            events.append(event)
            self._apply(event)
            number_of_beats -= 1
        publish(events)

    def count_heartbeats(self):
        return self._count_heartbeats

    @staticmethod
    def _mutator(initial, event):
        return example_mutator(initial, event)


@mutator
def example_mutator(initial, event, ):
    return mutate_entity(initial, event)


@example_mutator.register(Example.Heartbeat)
def heartbeat_mutator(self, event):
    self._validate_originator(event)
    assert isinstance(self, Example), self
    self._count_heartbeats += 1
    self._increment_version()
    return self


class AbstractExampleRepository(AbstractEntityRepository):
    pass


def create_new_example(foo='', a='', b=''):
    """
    Factory method for example entities.

    :rtype: Example
    """
    entity_id = uuid.uuid4()
    event = Example.Created(originator_id=entity_id, foo=foo, a=a, b=b)
    entity = Example.mutate(event=event)
    publish(event=event)
    return entity
