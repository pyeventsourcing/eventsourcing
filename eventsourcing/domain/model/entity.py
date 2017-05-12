from abc import ABCMeta, abstractmethod, abstractproperty

from six import with_metaclass

from eventsourcing.domain.model.decorators import mutator
from eventsourcing.domain.model.events import AttributeChanged, Created, Discarded, DomainEvent, \
    EventWithOriginatorID, EventWithOriginatorVersion, EventWithTimestamp, QualnameABC, publish
from eventsourcing.exceptions import EntityIsDiscarded, MismatchedOriginatorIDError, \
    MismatchedOriginatorVersionError, MutatorRequiresTypeNotInstance
from eventsourcing.utils.time import timestamp_from_uuid


class DomainEntity(QualnameABC):
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
        return type(self) == type(other) and self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)

    @property
    def id(self):
        return self._id

    def change_attribute(self, name, value, **kwargs):
        """
        Changes given attribute of the entity, by constructing
        and applying an AttributeChanged event.
        """
        self._assert_not_discarded()
        event = self.AttributeChanged(
            name=name,
            value=value,
            originator_id=self._id,
            **kwargs
        )
        self._apply_and_publish(event)

    def discard(self, **kwargs):
        self._assert_not_discarded()
        event = self.Discarded(originator_id=self._id, **kwargs)
        self._apply_and_publish(event)

    def _validate_originator(self, event):
        """
        Checks the event originated from (was published by) this entity.
        """
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

    def _assert_not_discarded(self):
        if self._is_discarded:
            raise EntityIsDiscarded("Entity is discarded")

    def _apply_and_publish(self, event):
        """
        Applies event, by mutating self with event and then publishing event.

        Must be an object method, since subclass AggregateRoot._publish()
        will append events to a list internal to the entity object, hence
        it needs to work with an instance rather than the type.
        """
        self._mutate(initial=self, event=event)
        self._publish(event)

    @classmethod
    def _mutate(cls, initial, event):
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
    def _mutate(cls, initial, event):
        """
        Calls the mutate() method of the event.

        Passes cls if initial is None, so that handler of Created
        events can construct an entity object with the subclass.
        """
        return event.mutate(initial or cls)


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

    def __init__(self, originator_version, **kwargs):
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
                ("Event originated from entity at version {}, "
                 "but entity is currently at version {}. "
                 "Event type: '{}', entity type: '{}', entity ID: '{}'"
                 "".format(self._version, event.originator_version,
                           type(event).__name__, type(self).__name__, self._id)
                 )
            )

    def change_attribute(self, name, value, **kwargs):
        return super(VersionedEntity, self).change_attribute(
            name, value, originator_version=self._version, **kwargs)

    def discard(self, **kwargs):
        return super(VersionedEntity, self).discard(
            originator_version=self._version, **kwargs)


class TimestampedEntity(DomainEntity):
    class Event(EventWithTimestamp, DomainEntity.Event):
        """Layer supertype."""

    class Created(Event, DomainEntity.Created):
        """Published when a TimestampedEntity is created."""

    class AttributeChanged(Event, DomainEntity.AttributeChanged):
        """Published when a TimestampedEntity is changed."""

    class Discarded(Event, DomainEntity.Discarded):
        """Published when a TimestampedEntity is discarded."""

    def __init__(self, timestamp, **kwargs):
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
    def __init__(self, event_id, **kwargs):
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
def _(self, event):
    assert isinstance(self, DomainEntity), self
    self._validate_originator(event)
    self._is_discarded = True
    if isinstance(event, TimestampedEntity.Discarded):
        self._last_modified_on = event.timestamp
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

    @abstractproperty
    def event_store(self):
        """
        Returns event store object used by this repository.
        """
