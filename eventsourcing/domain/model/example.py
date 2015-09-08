from abc import ABCMeta, abstractmethod
import uuid

from six import with_metaclass

from eventsourcing.domain.model.entity import EventSourcedEntity, eventsourcedproperty
from eventsourcing.domain.model.events import publish


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

    def __init__(self, a, b, **kwargs):
        super(Example, self).__init__(**kwargs)
        self._a = a
        self._b = b

    @eventsourcedproperty
    def a(self):
        return self._a

    @eventsourcedproperty()
    def b(self):
        return self._b



class Repository(with_metaclass(ABCMeta)):
    
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
    entity = Example.mutator(entity=Example, event=event)
    publish(event=event)
    return entity
