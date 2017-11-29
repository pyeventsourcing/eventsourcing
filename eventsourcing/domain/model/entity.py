"""
The entity module provides base classes for domain entities.
"""
from abc import ABCMeta, abstractmethod, abstractproperty

from six import with_metaclass

from eventsourcing.domain.model.decorators import mutator
from eventsourcing.domain.model.events import AttributeChanged, Created, Discarded, DomainEvent, \
    EventWithOriginatorID, EventWithOriginatorVersion, EventWithTimestamp, QualnameABC, publish
from eventsourcing.exceptions import EntityIsDiscarded, OriginatorIDError, \
    OriginatorVersionError, MutatorRequiresTypeNotInstance
from eventsourcing.utils.time import timestamp_from_uuid


class DomainEntity(QualnameABC):
    """Base class for domain entities."""

    class Event(EventWithOriginatorID, DomainEvent):
        """Supertype for events of domain entities."""

    class Created(Event, Created):
        """Published when a DomainEntity is created."""

    class AttributeChanged(Event, AttributeChanged):
        """Published when a DomainEntity is discarded."""

    class Discarded(Event, Discarded):
        """Published when a DomainEntity is discarded."""

    def __init__(self, id):
        self._id = id
        self._is_discarded = False

    def __eq__(self, other):
        return type(self) == type(other) and self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)

    @property
    def id(self):
        return self._id

    def change_attribute(self, name, value, **kwargs):
        """
        Changes named attribute with the given value, by triggering an AttributeChanged event.
        """
        kwargs['name'] = name
        kwargs['value'] = value
        self._trigger(self.AttributeChanged, **kwargs)

    def discard(self, **kwargs):
        """
        Discards self, by triggering a Discarded event.
        """
        self._trigger(self.Discarded, **kwargs)

    def _trigger(self, event_class, **kwargs):
        """
        Constructs, applies, and publishes domain event of given class, with given kwargs.
        """
        self._assert_not_discarded()
        event = event_class(originator_id=self._id, **kwargs)
        self._apply_and_publish(event)

    def _validate_originator(self, event):
        """
        Checks the event's originator ID matches this entity's ID.
        """
        if self._id != event.originator_id:
            raise OriginatorIDError(
                "'{}' not equal to event originator ID '{}'"
                "".format(self.id, event.originator_id)
            )

    def _assert_not_discarded(self):
        if self._is_discarded:
            raise EntityIsDiscarded("Entity is discarded")

    def _apply_and_publish(self, event):
        """
        Applies event to self and published event.

        Must be an object method, since subclass AggregateRoot._publish()
        will append events to a list internal to the entity object, hence
        it needs to work with an instance rather than the type.
        """
        self._apply(event)
        self._publish(event)

    def _apply(self, event):
        """
        Applies given event to self.

        Must be an object method, so that self is an object instance.
        """
        self._mutate(initial=self, event=event)

    @classmethod
    def _mutate(cls, initial=None, event=None):
        """
        Calls a mutator function with given entity and event.

        Passes cls if initial is None, so that Created event
        handler can construct an entity object with the correct
        subclass.

        Please override or extend in subclasses that extend or
        replace the mutate_entity() function, so that the correct
        mutator function will be invoked.
        """
        return mutate_entity(initial or cls, event)

    def _publish(self, event):
        """
        Publishes event for subscribers in the application.
        """
        publish(event)


class WithReflexiveMutator(DomainEntity):
    """
    Implements an entity mutator function by dispatching to the
    event itself all calls to mutate an entity with an event.

    This is an alternative to using an independent mutator function
    implemented with the @mutator decorator, or an if-else block.
    """

    @classmethod
    def _mutate(cls, initial=None, event=None):
        """
        Attempts to call the mutate() method of given event.

        Passes cls if initial is None, so that handler of Created
        events can construct an entity object with the subclass.
        """
        if hasattr(event, 'mutate') and callable(event.mutate):
            entity = event.mutate(initial or cls)
        else:
            entity = super(WithReflexiveMutator, cls)._mutate(initial, event)
        return entity


class VersionedEntity(DomainEntity):
    class Event(EventWithOriginatorVersion, DomainEntity.Event):
        """Supertype for events of versioned entities."""

    class Created(Event, DomainEntity.Created):
        """Published when a VersionedEntity is created."""
        def __init__(self, originator_version=0, **kwargs):
            super(VersionedEntity.Created, self).__init__(originator_version=originator_version, **kwargs)

    class AttributeChanged(Event, DomainEntity.AttributeChanged):
        """Published when a VersionedEntity is changed."""

    class Discarded(Event, DomainEntity.Discarded):
        """Published when a VersionedEntity is discarded."""

    def __init__(self, version=0, **kwargs):
        super(VersionedEntity, self).__init__(**kwargs)
        self._version = version

    @property
    def version(self):
        return self._version

    def _increment_version(self):
        if self._version is not None:
            self._version += 1

    def _validate_originator(self, event):
        """
        Also checks the event's originator version matches this entity's version.
        """
        super(VersionedEntity, self)._validate_originator(event)
        if self._version != event.originator_version:
            raise OriginatorVersionError(
                ("Event originated from entity at version {}, "
                 "but entity is currently at version {}. "
                 "Event type: '{}', entity type: '{}', entity ID: '{}'"
                 "".format(event.originator_version, self._version,
                           type(event).__name__, type(self).__name__, self._id)
                 )
            )

    def _trigger(self, event_class, **kwargs):
        """
        Triggers domain event with entity's version number.
        """
        kwargs['originator_version'] = self.version
        return super(VersionedEntity, self)._trigger(event_class, **kwargs)


class TimestampedEntity(DomainEntity):
    class Event(EventWithTimestamp, DomainEntity.Event):
        """Supertype for events of timestamped entities."""

    class Created(Event, DomainEntity.Created):
        """Published when a TimestampedEntity is created."""

    class AttributeChanged(Event, DomainEntity.AttributeChanged):
        """Published when a TimestampedEntity is changed."""

    class Discarded(Event, DomainEntity.Discarded):
        """Published when a TimestampedEntity is discarded."""

    def __init__(self, timestamp, **kwargs):
        super(TimestampedEntity, self).__init__(**kwargs)
        self._created_on = timestamp
        self._last_modified = timestamp

    @property
    def created_on(self):
        return self._created_on

    @property
    def last_modified(self):
        return self._last_modified


class TimeuuidedEntity(DomainEntity):
    def __init__(self, event_id, **kwargs):
        super(TimeuuidedEntity, self).__init__(**kwargs)
        self._initial_event_id = event_id
        self._last_event_id = event_id

    @property
    def created_on(self):
        return timestamp_from_uuid(self._initial_event_id)

    @property
    def last_modified(self):
        return timestamp_from_uuid(self._last_event_id)


class TimestampedVersionedEntity(TimestampedEntity, VersionedEntity):
    class Event(TimestampedEntity.Event, VersionedEntity.Event):
        """Supertype for events of timestamped, versioned entities."""

    class Created(Event, TimestampedEntity.Created, VersionedEntity.Created):
        """Published when a TimestampedVersionedEntity is created."""

    class AttributeChanged(Event, TimestampedEntity.AttributeChanged, VersionedEntity.AttributeChanged):
        """Published when a TimestampedVersionedEntity is created."""

    class Discarded(Event, TimestampedEntity.Discarded, VersionedEntity.Discarded):
        """Published when a TimestampedVersionedEntity is discarded."""


class TimeuuidedVersionedEntity(TimeuuidedEntity, VersionedEntity):
    pass


@mutator
def mutate_entity(initial, event):
    """Entity mutator function. Mutates initial state by the event.

    Different handlers are registered for different types of event.
    """
    raise NotImplementedError("Event type not supported: {}".format(type(event)))


@mutate_entity.register(DomainEntity.Created)
def _(cls, event):
    assert isinstance(event, Created), event
    if not isinstance(cls, type):
        msg = ("Mutator for Created event requires object type: {}".format(type(cls)))
        raise MutatorRequiresTypeNotInstance(msg)
    constructor_args = event.__dict__.copy()
    constructor_args['id'] = constructor_args.pop('originator_id')
    if 'originator_version' in constructor_args:
        constructor_args['version'] = constructor_args.pop('originator_version')
    try:
        self = cls(**constructor_args)
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
        self._last_modified = event.timestamp
    if isinstance(event, VersionedEntity.AttributeChanged):
        self._increment_version()
    return self


@mutate_entity.register(DomainEntity.Discarded)
def _(self, event):
    assert isinstance(self, DomainEntity), self
    self._validate_originator(event)
    self._is_discarded = True
    if isinstance(event, TimestampedEntity.Discarded):
        self._last_modified = event.timestamp
    if isinstance(event, VersionedEntity.Discarded):
        self._increment_version()
    return None


class AbstractEntityRepository(with_metaclass(ABCMeta)):
    def __init__(self, *args, **kwargs):
        pass

    @abstractmethod
    def __getitem__(self, entity_id):
        """
        Returns entity for given ID.
        """

    @abstractmethod
    def get_entity(self, entity_id):
        """
        Returns entity for given ID.
        """

    @abstractmethod
    def __contains__(self, entity_id):
        """
        Returns True or False, according to whether or not entity exists.
        """

    @property
    @abstractmethod
    def event_store(self):
        """
        Returns event store object used by this repository.
        """
