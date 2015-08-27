from abc import ABCMeta, abstractmethod
import uuid
from eventsourcing.domain.model.events import DomainEvent, publish


class Example(object):

    class Event(DomainEvent):

        def __init__(self, a, b, **kwargs):
            super().__init__(a=a, b=b, **kwargs)

        @property
        def a(self):
            return self.__dict__['a']

        @property
        def b(self):
            return self.__dict__['b']

    def __init__(self, event):
        assert isinstance(event, Example.Event), event
        self.id = event.entity_id
        self.a = event.a
        self.b = event.b
        self.created_on = event.timestamp


example_mutator = lambda entity, event: Example(event)


class Repository(metaclass=ABCMeta):
    
    @abstractmethod
    def __getitem__(self, item):
        pass


def register_new_example(a, b):
    """
    Factory method for example entities.
    """
    entity_id = uuid.uuid4().hex
    event = Example.Event(entity_id=entity_id, a=a, b=b)
    entity = example_mutator(None, event)
    publish(event)
    return entity
