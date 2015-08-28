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

    def __init__(self, a, b, **kwargs):
        super().__init__(**kwargs)
        self._a = a
        self._b = b

    @property
    def a(self):
        return self._a

    @a.setter
    def a(self, value):
        self._set_event_sourced_attribute_value(name='_a', value=value)

    @property
    def b(self):
        return self._b

    @b.setter
    def b(self, value):
        self._set_event_sourced_attribute_value(name='_b', value=value)


class Repository(metaclass=ABCMeta):
    
    @abstractmethod
    def __getitem__(self, item):
        """Returns example entity for given ID.
        """


def register_new_example(a, b):
    """
    Factory method for example entities.
    """
    entity_id = uuid.uuid4().hex
    event = Example.Created(entity_id=entity_id, a=a, b=b)
    entity = Example.mutator(self=Example, event=event)
    publish(event=event)
    return entity
