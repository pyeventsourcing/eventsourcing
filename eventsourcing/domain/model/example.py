from abc import ABCMeta, abstractmethod
import uuid

from eventsourcing.domain.model.entity import EventSourcedEntity
from eventsourcing.domain.model.events import publish


class Example(EventSourcedEntity):

    class Created(EventSourcedEntity.Created):

        def __init__(self, a, b, timestamp=None, entity_id=None, entity_version=0):
            super().__init__(a=a, b=b, timestamp=timestamp, entity_id=entity_id, entity_version=entity_version)

        @property
        def a(self):
            return self.__dict__['a']

        @property
        def b(self):
            return self.__dict__['b']

    class Discarded(EventSourcedEntity.Discarded):
        def __init__(self, entity_id, entity_version, timestamp=None):
            super().__init__(timestamp=timestamp, entity_id=entity_id, entity_version=entity_version)

    def __init__(self, event):
        super().__init__(event)
        self.a = event.a
        self.b = event.b

    def discard(self):
        self._assert_not_discarded()
        event = Example.Discarded(entity_id=self._id, entity_version=self._version)
        self._apply(event)
        publish(event)

    def _apply(self, event):
        example_mutator(self, event)


def example_mutator(entity=None, event=None):
    if isinstance(event, Example.Created):
        entity = Example(event)
        entity._increment_version()
        return entity
    elif isinstance(event, Example.Discarded):
        entity._validate_originator(event)
        entity._is_discarded = True
        entity._increment_version()
        return None
    else:
        raise NotImplementedError(repr(event))


class Repository(metaclass=ABCMeta):
    
    @abstractmethod
    def __getitem__(self, item):
        pass


def register_new_example(a, b):
    """
    Factory method for example entities.
    """
    entity_id = uuid.uuid4().hex
    event = Example.Created(entity_id=entity_id, entity_version=0, a=a, b=b)
    entity = example_mutator(event=event)
    publish(event=event)
    return entity
