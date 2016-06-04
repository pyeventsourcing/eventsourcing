from eventsourcing.domain.model.exceptions import ConsistencyError

try:
    # Python 3.4+
    from functools import singledispatch
except ImportError:
    from singledispatch import singledispatch

from abc import ABCMeta, abstractmethod
from inspect import isfunction

from six import with_metaclass

from eventsourcing.domain.model.events import DomainEvent, publish, QualnameABCMeta


class EventSourcedEntity(with_metaclass(QualnameABCMeta)):

    __snapshot_threshold__ = None

    class Created(DomainEvent):
        def __init__(self, entity_version=0, **kwargs):
            super(EventSourcedEntity.Created, self).__init__(entity_version=entity_version, **kwargs)

    class AttributeChanged(DomainEvent):
        pass

    class Discarded(DomainEvent):
        pass

    def __init__(self, entity_id, entity_version, timestamp):
        self._id = entity_id
        self._version = entity_version
        self._is_discarded = False
        self._created_on = timestamp

    def _increment_version(self):
        self._version += 1

    def _assert_not_discarded(self):
        if self._is_discarded:
            raise AssertionError("Entity is discarded")

    @property
    def id(self):
        return self._id

    def _validate_originator(self, event):
        # Check event originator's entity ID matches our own ID.
        if self._id != event.entity_id:
            raise ConsistencyError("Entity ID '{}' not equal to event's entity ID '{}'"
                                       "".format(self.id, event.entity_id))

        # Check event originator's version number matches our own version number.
        if self._version != event.entity_version:
            raise ConsistencyError("Entity version '{}' not equal to event's entity version '{}'"
                                       "".format(self._version, event.entity_version))

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def _change_attribute(self, name, value):
        self._assert_not_discarded()
        event = self.AttributeChanged(name=name, value=value, entity_id=self._id, entity_version=self._version)
        self._apply(event)
        publish(event)

    def discard(self):
        self._assert_not_discarded()
        event = self.Discarded(entity_id=self._id, entity_version=self._version)
        self._apply(event)
        publish(event)

    def _apply(self, event):
        self.mutate(event=event, entity=self)

    @classmethod
    def mutate(cls, entity=None, event=None):
        initial = entity if entity is not None else cls
        return cls._mutator(event, initial)

    @staticmethod
    def _mutator(event, initial):
        return entity_mutator(event, initial)


@singledispatch
def entity_mutator(event, _):
    raise NotImplementedError("Event type not supported: {}".format(type(event)))


@entity_mutator.register(EventSourcedEntity.Created)
def created_mutator(event, cls):
    assert isinstance(event, DomainEvent)
    assert isinstance(cls, type), ("Expected type but got instance of: {}, possibly "
                                   "due to duplicate {} events for entity ID {}?"
                                   "".format(type(cls), type(event), event.entity_id))
    assert issubclass(cls, EventSourcedEntity), cls
    self = cls(**event.__dict__)
    self._increment_version()
    return self


@entity_mutator.register(EventSourcedEntity.AttributeChanged)
def attribute_changed_mutator(event, self):
    self._validate_originator(event)
    setattr(self, event.name, event.value)
    self._increment_version()
    return self


@entity_mutator.register(EventSourcedEntity.Discarded)
def discarded_mutator(event, self):
    self._validate_originator(event)
    self._is_discarded = True
    self._increment_version()
    return None


def mutableproperty(getter):
    if isfunction(getter):

        def setter(self, value):
            assert isinstance(self, EventSourcedEntity), type(self)
            name = '_' + getter.__name__
            self._change_attribute(name=name, value=value)

        return property(fget=getter, fset=setter)
    else:
        raise ValueError(repr(getter))


class EntityRepository(with_metaclass(ABCMeta)):

    @abstractmethod
    def __getitem__(self, entity_id):
        """Returns entity for given ID.
        """

    @abstractmethod
    def __contains__(self, entity_id):
        """Returns True or False, according to whether or not entity exists.
        """
