from abc import ABCMeta, abstractmethod
from inspect import isfunction

try:
    # Python 3.4+
    from functools import singledispatch
except ImportError:
    from singledispatch import singledispatch

from six import with_metaclass
from eventsourcing.domain.model.events import DomainEvent, publish, QualnameABCMeta


def make_stored_entity_id(id_prefix, entity_id):
    return id_prefix + '::' + entity_id


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
        assert not self._is_discarded

    @property
    def id(self):
        return self._id

    def _validate_originator(self, event):
        assert self.id == event.entity_id, (self.id, event.entity_id)
        assert self._version == event.entity_version, "{} != {}".format(self._version, event.entity_version)

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
        self.mutator(entity=self, event=event)

    @classmethod
    def mutator(cls, entity=None, event=None):
        return cls._mutator(event, entity if entity is not None else cls)

    @classmethod
    def _mutator(cls, event, entity):
        return mutator(event, entity)


@singledispatch
def mutator(event, _):
    raise NotImplementedError("Event type not supported: {}".format(event))


@mutator.register(EventSourcedEntity.Created)
def _(event, entity_class):
    assert not isinstance(entity_class, EventSourcedEntity), "Are there multiple Created events for the same ID? %s, %s" % (entity_class, event)
    assert issubclass(entity_class, EventSourcedEntity), "%s event handler requires domain class, got: %s" % (event, entity_class)
    entity = entity_class(**event.__dict__)
    entity._increment_version()
    return entity


@mutator.register(EventSourcedEntity.AttributeChanged)
def _(event, entity):
    entity._validate_originator(event)
    setattr(entity, event.name, event.value)
    entity._increment_version()
    return entity


@mutator.register(EventSourcedEntity.Discarded)
def _(event, entity):
    entity._validate_originator(event)
    entity._is_discarded = True
    entity._increment_version()
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
