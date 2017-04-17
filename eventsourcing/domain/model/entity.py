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

from eventsourcing.domain.model.events import publish, QualnameABCMeta, AggregateEvent


class EntityIDConsistencyError(ConsistencyError):
    pass


class EntityVersionConsistencyError(ConsistencyError):
    pass


class CreatedMutatorRequiresTypeNotInstance(ConsistencyError):
    pass


class EntityIsDiscarded(AssertionError):
    pass


class Created(AggregateEvent):
    def __init__(self, entity_version=0, **kwargs):
        super(Created, self).__init__(entity_version=entity_version, **kwargs)


class AttributeChanged(AggregateEvent):
    @property
    def name(self):
        return self.__dict__['name']

    @property
    def value(self):
        return self.__dict__['value']


class Discarded(AggregateEvent):
    pass


class DomainEntity(with_metaclass(QualnameABCMeta)):

    def __init__(self, entity_id):
        self._id = entity_id
        self._is_discarded = False

    def _assert_not_discarded(self):
        if self._is_discarded:
            raise EntityIsDiscarded("Entity is discarded")

    @property
    def id(self):
        return self._id

    def _validate_originator(self, event):
        self._validate_originator_id(event)

    def _validate_originator_id(self, event):
        """
        Checks the event's entity ID matches this entity's ID.
        """
        if self._id != event.entity_id:
            raise EntityIDConsistencyError(
                "Entity ID '{}' not equal to event's entity ID '{}'"
                "".format(self.id, event.entity_id)
            )

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def _change_attribute(self, name, value):
        self._assert_not_discarded()
        event_class = getattr(self, 'AttributeChanged', AttributeChanged)
        event = event_class(name=name, value=value, entity_id=self._id, entity_version=self._version)
        self._apply(event)
        publish(event)

    def discard(self):
        self._assert_not_discarded()
        event_class = getattr(self, 'Discarded', Discarded)
        event = event_class(entity_id=self._id, entity_version=self._version)
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


class WithReflexiveMutator(DomainEntity):
    """
    Implements an entity mutator function by dispatching all
    calls to mutate an entity with an event to the event itself.
    
    This is an alternative to using an independent mutator function
    implemented with singledispatch or an if-else block.
    """
    @classmethod
    def mutate(cls, entity=None, event=None):
        return event.apply(entity or cls)


class VersionedEntity(DomainEntity):

    def __init__(self, entity_version=None, **kwargs):
        super(VersionedEntity, self).__init__(**kwargs)
        self._version = entity_version

    @property
    def version(self):
        return self._version

    def _increment_version(self):
        if self._version is not None:
            self._version += 1

    def _validate_originator(self, event):
        super(VersionedEntity, self)._validate_originator(event)
        self._validate_originator_version(event)

    def _validate_originator_version(self, event):
        """
        Checks the event's entity version matches this entity's version.
        """
        if self._version != event.entity_version:
            raise EntityVersionConsistencyError(
                ("Event version '{}' not equal to entity version '{}', "
                 "event type: '{}', entity type: '{}', entity ID: '{}'"
                 "".format(event.entity_version, self._version,
                           type(event).__name__, type(self).__name__, self._id)
                 )
            )


class TimestampedEntity(DomainEntity):
    def __init__(self, timestamp=None, **kwargs):
        super(TimestampedEntity, self).__init__(**kwargs)
        self._created_on = timestamp
        self._last_modified_on = timestamp

    @property
    def created_on(self):
        return self._created_on

    @property
    def last_modified_on(self):
        return self._last_modified_on


class TimeuuidedEntity(DomainEntity):
    def __init__(self, event_id=None, **kwargs):
        super(TimeuuidedEntity, self).__init__(**kwargs)
        self._initial_event_id = event_id
        self._last_event_id = event_id

    @property
    def created_on(self):
        return timestamp_from_uuid(self._initial_event_id)

    @property
    def last_modified_on(self):
        return timestamp_from_uuid(self._last_event_id)


class TimestampedVersionedEntity(TimestampedEntity, VersionedEntity):
    pass


class TimeuuidedVersionedEntity(TimeuuidedEntity, VersionedEntity):
    pass


@singledispatch
def entity_mutator(event, _):
    raise NotImplementedError("Event type not supported: {}".format(type(event)))


@entity_mutator.register(Created)
def created_mutator(event, cls):
    assert isinstance(event, Created), event
    if not isinstance(cls, type):
        msg = ("Mutator for Created event requires entity type not instance: {} "
               "(event entity id: {}, event type: {})"
               "".format(type(cls), event.entity_id, type(event)))
        raise CreatedMutatorRequiresTypeNotInstance(msg)
    assert issubclass(cls, TimestampedVersionedEntity), cls
    try:
        self = cls(**event.__dict__)
    except TypeError as e:
        raise TypeError("Class {} {}. Given {} from event type {}".format(cls, e, event.__dict__, type(event)))
    self._increment_version()
    return self


@entity_mutator.register(AttributeChanged)
def attribute_changed_mutator(event, self):
    assert isinstance(self, TimestampedVersionedEntity), self
    self._validate_originator(event)
    setattr(self, event.name, event.value)
    self._last_modified_on = event.timestamp
    self._increment_version()
    return self


@entity_mutator.register(Discarded)
def discarded_mutator(event, self):
    assert isinstance(self, TimestampedVersionedEntity), self
    self._validate_originator(event)
    self._is_discarded = True
    self._increment_version()
    return None


def attribute(getter):
    """
    When used as a method decorator, returns a property object
    with the method as the getter and a setter defined to call
    instance method _change_attribute(), which publishes an
    AttributeChanged event.
    """
    if isfunction(getter):
        def setter(self, value):
            assert isinstance(self, TimestampedVersionedEntity), type(self)
            name = '_' + getter.__name__
            self._change_attribute(name=name, value=value)

        def new_getter(self):
            assert isinstance(self, TimestampedVersionedEntity), type(self)
            name = '_' + getter.__name__
            return getattr(self, name)

        return property(fget=new_getter, fset=setter)
    else:
        raise ProgrammingError("Expected a function, got: {}".format(repr(getter)))


class AbstractEntityRepository(with_metaclass(ABCMeta)):
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


class Aggregate(TimestampedVersionedEntity):
    """
    For aggregates in Domain Driven Design.
    """


class AggregateRepository(AbstractEntityRepository):
    """
    For aggregate repositories in Domain Driven Design.
    """
