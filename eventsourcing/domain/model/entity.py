from abc import ABCMeta, abstractmethod
from inspect import isfunction

from six import with_metaclass

from eventsourcing.domain.model.events import AttributeChanged, Created, Discarded, DomainEvent, \
    EventWithOriginatorID, EventWithOriginatorVersion, EventWithTimestamp, QualnameABCMeta, mutator, publish
from eventsourcing.exceptions import EntityIsDiscarded, MismatchedOriginatorIDError, \
    MismatchedOriginatorVersionError, MutatorRequiresTypeNotInstance, ProgrammingError
from eventsourcing.utils.time import timestamp_from_uuid


class DomainEntity(with_metaclass(QualnameABCMeta)):
    class Event(EventWithOriginatorID, DomainEvent):
        """Layer supertype."""

    class Created(Event, Created):
        """Published when a DomainEntity is created."""

    class AttributeChanged(Event, AttributeChanged):
        """Published when a DomainEntity is discarded."""

    class Discarded(Event, Discarded):
        """Published when a DomainEntity is discarded."""

    def __init__(self, originator_id):
        self._id = originator_id
        self._is_discarded = False

    def __eq__(self, other):
        return (other is not None) and (self.__dict__ == other.__dict__) and (type(self) == type(other))

    def __ne__(self, other):
        return not self.__eq__(other)

    @property
    def id(self):
        return self._id

    def _validate_originator(self, event):
        self._validate_originator_id(event)

    def _validate_originator_id(self, event):
        """
        Checks the event's entity ID matches this entity's ID.
        """
        if self._id != event.originator_id:
            raise MismatchedOriginatorIDError(
                "'{}' not equal to event originator ID '{}'"
                "".format(self.id, event.originator_id)
            )

    def _apply(self, event):
        self.mutate(event=event, entity=self)

    def _publish(self, event):
        publish(event)

    @classmethod
    def mutate(cls, entity=None, event=None):
        initial = entity if entity is not None else cls
        return cls._mutator(initial, event)

    @staticmethod
    def _mutator(initial, event):
        return mutate_entity(initial, event)

    def _change_attribute(self, name, value):
        self._assert_not_discarded()
        event = self._construct_attribute_changed_event(name, value)
        self._apply(event)
        self._publish(event)

    def discard(self):
        self._assert_not_discarded()
        event = self._construct_discarded_event()
        self._apply(event)
        self._publish(event)

    def _construct_attribute_changed_event(self, name, value):
        event = self.AttributeChanged(
            name=name,
            value=value,
            originator_id=self._id,
        )
        return event

    def _construct_discarded_event(self):
        return self.Discarded(originator_id=self._id)

    def _assert_not_discarded(self):
        if self._is_discarded:
            raise EntityIsDiscarded("Entity is discarded")


class WithReflexiveMutator(DomainEntity):
    """
    Implements an entity mutator function by dispatching all
    calls to mutate an entity with an event to the event itself.
    
    This is an alternative to using an independent mutator function
    implemented with the @mutator decorator, or an if-else block.
    """

    @classmethod
    def mutate(cls, entity=None, event=None):
        return event.apply(entity or cls)


class VersionedEntity(DomainEntity):
    class Event(EventWithOriginatorVersion, DomainEntity.Event):
        """Layer supertype."""

    class Created(Event, DomainEntity.Created):
        """Published when a VersionedEntity is created."""

        def __init__(self, originator_version=0, **kwargs):
            super(Created, self).__init__(originator_version=originator_version, **kwargs)

    class AttributeChanged(Event, DomainEntity.AttributeChanged):
        """Published when a VersionedEntity is changed."""

    class Discarded(Event, DomainEntity.Discarded):
        """Published when a VersionedEntity is discarded."""

    def __init__(self, originator_version=None, **kwargs):
        super(VersionedEntity, self).__init__(**kwargs)
        self._version = originator_version

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
        if self._version != event.originator_version:
            raise MismatchedOriginatorVersionError(
                ("Event originated from entity at version {}, but entity is currently at version {}. "
                 "Event type: '{}', entity type: '{}', entity ID: '{}'"
                 "".format(self._version, event.originator_version,
                           type(event).__name__, type(self).__name__, self._id)
                 )
            )

    def _construct_attribute_changed_event(self, name, value):
        event = self.AttributeChanged(
            name=name,
            value=value,
            originator_id=self._id,
            originator_version=self._version,
        )
        return event

    def _construct_discarded_event(self):
        return self.Discarded(
            originator_id=self._id,
            originator_version=self._version,
        )


class TimestampedEntity(DomainEntity):
    class Event(EventWithTimestamp, DomainEntity.Event):
        """Layer supertype."""

    class Created(Event, DomainEntity.Created):
        """Published when a TimestampedEntity is created."""

    class AttributeChanged(Event, DomainEntity.AttributeChanged):
        """Published when a TimestampedEntity is changed."""

    class Discarded(Event, DomainEntity.Discarded):
        """Published when a TimestampedEntity is discarded."""

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
    class Event(TimestampedEntity.Event, VersionedEntity.Event):
        """Layer supertype."""

    class Created(Event, TimestampedEntity.Created, VersionedEntity.Created):
        """Published when a TimestampedVersionedEntity is created."""

    class AttributeChanged(Event, TimestampedEntity.AttributeChanged, VersionedEntity.AttributeChanged):
        """Published when a TimestampedVersionedEntity is created."""

    class Discarded(Event, TimestampedEntity.Discarded, VersionedEntity.Discarded):
        """Published when a TimestampedVersionedEntity is discarded."""


class TimeuuidedVersionedEntity(TimeuuidedEntity, VersionedEntity):
    pass


@mutator
def mutate_entity(_, event):
    raise NotImplementedError("Event type not supported: {}".format(type(event)))


@mutate_entity.register(DomainEntity.Created)
def created_mutator(cls, event):
    assert isinstance(event, Created), event
    if not isinstance(cls, type):
        msg = ("Mutator for Created event requires object type: {}".format(type(cls)))
        raise MutatorRequiresTypeNotInstance(msg)
    try:
        self = cls(**event.__dict__)
    except TypeError as e:
        raise TypeError("Class {} {}. Given {} from event type {}"
                        "".format(cls, e, event.__dict__, type(event)))
    if isinstance(event, VersionedEntity.Created):
        self._increment_version()
    return self


@mutate_entity.register(DomainEntity.AttributeChanged)
def _(self, event):
    self._validate_originator(event)
    setattr(self, event.name, event.value)
    if isinstance(event, TimestampedEntity.AttributeChanged):
        self._last_modified_on = event.timestamp
    if isinstance(event, VersionedEntity.AttributeChanged):
        self._increment_version()
    return self


@mutate_entity.register(DomainEntity.Discarded)
def discarded_mutator(self, event):
    assert isinstance(self, DomainEntity), self
    self._validate_originator(event)
    self._is_discarded = True
    if isinstance(event, TimestampedEntity.Discarded):
        self._last_modified_on = event.timestamp
    if isinstance(event, VersionedEntity.Discarded):
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
            assert isinstance(self, DomainEntity), type(self)
            name = '_' + getter.__name__
            self._change_attribute(name=name, value=value)

        def new_getter(self):
            assert isinstance(self, DomainEntity), type(self)
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
