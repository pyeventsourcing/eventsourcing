from abc import ABCMeta, abstractmethod
import uuid

from eventsourcing.domain.model.entity import EventSourcedEntity
from eventsourcing.domain.model.events import publish


class Example(EventSourcedEntity):

    class Created(EventSourcedEntity.Created):

        @property
        def a(self):
            return self.__dict__['a']

        @property
        def b(self):
            return self.__dict__['b']

    def __init__(self, event):
        super().__init__(event)
        self.a = event.a
        self.b = event.b

    @staticmethod
    def mutator(self=None, event=None):
        event_type = type(event)
        if event_type == Example.Created:
            assert self is None, self
            self = Example(event)
            self._increment_version()
            return self
        elif event_type == Example.Discarded:
            self._validate_originator(event)
            self._is_discarded = True
            self._increment_version()
            return None
        else:
            raise NotImplementedError(repr(event_type))


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
    entity = Example.mutator(event=event)
    publish(event=event)
    return entity
