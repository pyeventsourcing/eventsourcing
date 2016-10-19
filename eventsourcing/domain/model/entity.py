from eventsourcing.exceptions import ConsistencyError, ProgrammingError
from eventsourcing.utils.time import timestamp_from_uuid

try:
    # Python 3.4+
    from functools import singledispatch
except ImportError:
    from singledispatch import singledispatch

from abc import ABCMeta, abstractmethod
from inspect import isfunction
from six import with_metaclass

from eventsourcing.domain.model.events import DomainEvent, publish, QualnameABCMeta


class EntityIDConsistencyError(ConsistencyError):
    pass


class EntityVersionConsistencyError(ConsistencyError):
    pass


class CreatedMutatorRequiresTypeNotInstance(ConsistencyError):
    pass


class EntityIsDiscarded(AssertionError):
    pass


class EventSourcedEntity(with_metaclass(QualnameABCMeta)):

    # The page size by which events are retrieved. If this
    # value is set to a positive integer, the events of
    # the entity will be retrieved in pages, using a series
    # of queries, rather than with one potentially large query.
    __page_size__ = None

    # If the entity won't have very many events, marking the entity as
    # "short" by setting __is_short__ value equal to True will mean
    # the fastest path for getting all the events is used.
    __is_short__ = False

    # This should be enabled for models that have their consistency
    # protected against concurrency errors, with e.g. optimistic
    # concurrency control. See 'always_write_entity_version' constructor
    # argument in EventSourcingApplication and StoredEventRepo classes.
    __always_validate_originator_version__ = False

    class Created(DomainEvent):
        def __init__(self, entity_version=0, **kwargs):
            super(EventSourcedEntity.Created, self).__init__(entity_version=entity_version, **kwargs)

    class AttributeChanged(DomainEvent):
        pass

    class Discarded(DomainEvent):
        pass

    def __init__(self, entity_id, entity_version, domain_event_id):
        self._id = entity_id
        self._version = entity_version
        self._is_discarded = False
        self._initial_event_id = domain_event_id

    def _increment_version(self):
        if self._version is not None:
            self._version += 1

    def _assert_not_discarded(self):
        if self._is_discarded:
            raise EntityIsDiscarded("Entity is discarded")

    @property
    def id(self):
        return self._id

    @property
    def version(self):
        return self._version

    @property
    def created_on(self):
        return timestamp_from_uuid(self._initial_event_id)

    def _validate_originator(self, event):
        # Check event's entity ID matches this entity's ID.
        if self._id != event.entity_id:
            raise EntityIDConsistencyError("Entity ID '{}' not equal to event's entity ID '{}'"
                                           "".format(self.id, event.entity_id))

        # Check event's entity version matches this entity's version.
        if self.__always_validate_originator_version__ and self._version != event.entity_version:
            raise EntityVersionConsistencyError(
                "Event version '{}' not equal to entity version '{}', event type: '{}', entity type: '{}', entity ID: '{}'"
                "".format(event.entity_version, self._version, type(event).__name__, type(self).__name__, self._id))

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
    assert isinstance(event, DomainEvent), event
    if not isinstance(cls, type):
        msg = ("Mutator for Created event requires entity type not instance: {} "
               "(event entity id: {}, event type: {})"
               "".format(type(cls), event.entity_id, type(event)))
        raise CreatedMutatorRequiresTypeNotInstance(msg)
    assert issubclass(cls, EventSourcedEntity), cls
    self = cls(**event.__dict__)
    self._increment_version()
    return self


@entity_mutator.register(EventSourcedEntity.AttributeChanged)
def attribute_changed_mutator(event, self):
    assert isinstance(self, EventSourcedEntity), self
    self._validate_originator(event)
    setattr(self, event.name, event.value)
    self._increment_version()
    return self


@entity_mutator.register(EventSourcedEntity.Discarded)
def discarded_mutator(event, self):
    assert isinstance(self, EventSourcedEntity), self
    self._validate_originator(event)
    self._is_discarded = True
    self._increment_version()
    return None


def mutableproperty(getter):
    """
    When used as a class method decorator, returns a property object
    with the method as the getter and a setter defined to call instance
    method _change_attribute(), which publishes an AttributeChanged event.
    """
    if isfunction(getter):
        def setter(self, value):
            assert isinstance(self, EventSourcedEntity), type(self)
            name = '_' + getter.__name__
            self._change_attribute(name=name, value=value)

        def new_getter(self):
            assert isinstance(self, EventSourcedEntity), type(self)
            name = '_' + getter.__name__
            return getattr(self, name)

        return property(fget=new_getter, fset=setter)
    else:
        raise ProgrammingError("Expected a function, got: {}".format(repr(getter)))


class EntityRepository(with_metaclass(ABCMeta)):

    @abstractmethod
    def __getitem__(self, entity_id):
        """
        Returns entity for given ID.
        """

    @abstractmethod
    def __contains__(self, entity_id):
        """
        Returns True or False, according to whether or not entity exists.
        """
