"""
The entity module provides base classes for domain entities.
"""
import hashlib
import json
from abc import ABCMeta, abstractmethod, abstractproperty
from uuid import uuid4

from six import with_metaclass

from eventsourcing.domain.model.decorators import mutator
from eventsourcing.domain.model.events import AttributeChanged, Created, Discarded, DomainEvent, \
    EventWithOriginatorID, EventWithOriginatorVersion, EventWithTimestamp, QualnameABC, publish, GENESIS_HASH
from eventsourcing.exceptions import EntityIsDiscarded, OriginatorIDError, \
    OriginatorVersionError, MutatorRequiresTypeNotInstance, OriginatorHeadError, EventHashError
from eventsourcing.utils.time import timestamp_from_uuid
from eventsourcing.utils.topic import get_topic, resolve_topic
from eventsourcing.utils.transcoding import ObjectJSONEncoder


class DomainEntity(QualnameABC):
    """Base class for domain entities."""

    class Event(EventWithOriginatorID, DomainEvent):
        """Supertype for events of domain entities."""

        json_encoder_class = ObjectJSONEncoder

        def __init__(self, originator_head, **kwargs):
            kwargs['originator_head'] = originator_head
            super(DomainEntity.Event, self).__init__(**kwargs)

            # Seal the event state.
            assert 'event_hash' not in self.__dict__
            self.__dict__['event_hash'] = self.hash(self.__dict__)

        @property
        def originator_head(self):
            return self.__dict__['originator_head']

        @property
        def event_hash(self):
            return self.__dict__['event_hash']

        def validate(self):
            state = self.__dict__.copy()
            event_hash = state.pop('event_hash')
            if event_hash != self.hash(state):
                raise EventHashError()

        @classmethod
        def hash(cls, *args):
            json_dump = json.dumps(
                args,
                separators=(',', ':'),
                sort_keys=True,
                cls=cls.json_encoder_class,
            )
            return hashlib.sha256(json_dump.encode()).hexdigest()

        def mutate(self, obj):
            self.validate()
            obj.validate_originator(self)
            obj.__head__ = self.event_hash
            return self._mutate(obj)

        def _mutate(self, aggregate):
            return aggregate

    class Created(Event, Created):
        """Published when a DomainEntity is created."""

        def __init__(self, originator_topic, **kwargs):
            kwargs['originator_topic'] = originator_topic
            assert 'originator_head' not in kwargs
            super(DomainEntity.Created, self).__init__(
                originator_head=GENESIS_HASH, **kwargs
            )

        @property
        def originator_topic(self):
            return self.__dict__['originator_topic']

        def mutate(self, cls=None):
            if cls is None:
                cls = resolve_topic(self.originator_topic)
            obj = cls(**self.constructor_kwargs())
            obj = super(DomainEntity.Created, self).mutate(obj)
            return obj

        def constructor_kwargs(self):
            kwargs = self.__dict__.copy()
            kwargs.pop('event_hash')
            kwargs.pop('originator_head')
            kwargs.pop('originator_topic')
            kwargs['id'] = kwargs.pop('originator_id')
            return kwargs

    class AttributeChanged(Event, AttributeChanged):
        """Published when a DomainEntity is discarded."""
        def mutate(self, obj):
            obj = super(DomainEntity.AttributeChanged, self).mutate(obj)
            setattr(obj, self.name, self.value)
            return obj

    class Discarded(Discarded, Event):
        """Published when a DomainEntity is discarded."""
        def mutate(self, obj):
            obj = super(DomainEntity.Discarded, self).mutate(obj)
            obj.set_is_discarded()
            return None

    def __init__(self, id):
        self._id = id
        self._is_discarded = False
        self.__head__ = GENESIS_HASH

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

    def set_is_discarded(self):
        self._is_discarded = True

    def _trigger(self, event_class, **kwargs):
        """
        Constructs, applies, and publishes domain event of given class, with given kwargs.
        """
        self._assert_not_discarded()
        kwargs['originator_head'] = self.__head__
        event = event_class(originator_id=self._id, **kwargs)
        self._apply_and_publish(event)

    def validate_originator(self, event):
        """
        Checks the event's originator ID matches this entity's ID.
        """
        self._validate_originator_id(event)
        self._validate_originator_head(event)

    def _validate_originator_id(self, event):
        if self._id != event.originator_id:
            raise OriginatorIDError(
                "'{}' not equal to event originator ID '{}'"
                "".format(self.id, event.originator_id)
            )

    def _validate_originator_head(self, event):
        """
        Checks the head hash matches the event originator hash.
        """
        if self.__head__ != event.originator_head:
            raise OriginatorHeadError(self.id, self.__head__, type(event))

    def _assert_not_discarded(self):
        if self._is_discarded:
            raise EntityIsDiscarded("Entity is discarded")

    def _apply_and_publish(self, event):
        """
        Applies event to self and published event.

        Must be an object method, since subclass AggregateRoot.publish()
        will append events to a list internal to the entity object, hence
        it needs to work with an instance rather than the type.
        """
        self._apply(event)
        self.publish(event)

    def _apply(self, event):
        """
        Applies given event to self.

        Must be an object method, so that self is an object instance.
        """
        event.mutate(self)

    def publish(self, event):
        """
        Publishes given event for subscribers in the application.

        :param event: domain event or list of events
        """
        self._publish_to_subscribers(event)

    def _publish_to_subscribers(self, event):
        """
        Actually dispatches given event to publish-subscribe mechanism.

        :param event: domain event or list of events
        """
        publish(event)

    @classmethod
    def create(cls, originator_id=None, **kwargs):
        if originator_id is None:
            originator_id = uuid4()
        event = cls.Created(
            originator_id=originator_id,
            originator_topic=get_topic(cls),
            **kwargs
        )
        obj = event.mutate()
        obj.publish(event)
        return obj


# class WithReflexiveMutator(DomainEntity):
#     """
#     Implements an entity mutator function by dispatching to the
#     event itself all calls to mutate an entity with an event.
#
#     This is an alternative to using an independent mutator function
#     implemented with the @mutator decorator, or an if-else block.
#     """
#
#     @classmethod
#     def _mutate(cls, initial=None, event=None):
#         """
#         Attempts to call the mutate() method of given event.
#
#         Passes cls if initial is None, so that handler of Created
#         events can construct an entity object with the subclass.
#         """
#         if hasattr(event, 'mutate') and callable(event.mutate):
#             entity = event.mutate(initial or cls)
#         else:
#             entity = super(WithReflexiveMutator, cls)._mutate(initial, event)
#         return entity
#

class VersionedEntity(DomainEntity):
    class Event(EventWithOriginatorVersion, DomainEntity.Event):
        """Supertype for events of versioned entities."""
        def mutate(self, obj):
            obj = super(VersionedEntity.Event, self).mutate(obj)
            if obj is not None:
                obj._increment_version()
            return obj

    class Created(DomainEntity.Created, Event):
        """Published when a VersionedEntity is created."""
        def __init__(self, originator_version=0, **kwargs):
            super(VersionedEntity.Created, self).__init__(originator_version=originator_version, **kwargs)

        def constructor_kwargs(self):
            kwargs = super(VersionedEntity.Created, self).constructor_kwargs()
            kwargs['version'] = kwargs.pop('originator_version')
            return kwargs

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

    def validate_originator(self, event):
        """
        Also checks the event's originator version matches this entity's version.
        """
        super(VersionedEntity, self).validate_originator(event)
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
    class Event(DomainEntity.Event, EventWithTimestamp):
        """Supertype for events of timestamped entities."""
        def mutate(self, obj):
            obj = super(TimestampedEntity.Event, self).mutate(obj)
            if obj is not None:
                assert isinstance(obj, TimestampedEntity), obj
                obj.set_last_modified(self.timestamp)
            return obj

    class Created(DomainEntity.Created, Event):
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

    def set_last_modified(self, last_modified):
        self._last_modified = last_modified


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

    class Created(TimestampedEntity.Created, VersionedEntity.Created, Event):
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
    constructor_args = event.__dict__.copy()
    # Make sure 'originator_topic' not in construct args.
    if 'originator_topic' in constructor_args:
        originator_topic = constructor_args.pop('originator_topic')
    else:
        originator_topic = None

    # Prefer the cls arg over the resolved originator topic.
    if cls is not None:
        # Check the 'cls' arg is an object class.
        if not isinstance(cls, type) or not issubclass(cls, object):
            msg = ("Mutator initial value is not a class: {}".format(type(cls)))
            raise MutatorRequiresTypeNotInstance(msg)
    else:
        assert originator_topic, "Mutator originator topic is required"
        cls = resolve_topic(originator_topic)

    # Pop originator_head and event_hash.
    if 'originator_head' in constructor_args:
        constructor_args.pop('originator_head')
    if 'event_hash' in constructor_args:
        constructor_args.pop('event_hash')

    # Map originator_id.
    constructor_args['id'] = constructor_args.pop('originator_id')

    # Map originator_version.
    if 'originator_version' in constructor_args:
        constructor_args['version'] = constructor_args.pop('originator_version')

    # Construct the entity object.
    try:
        obj = cls(**constructor_args)
    except TypeError as e:
        raise TypeError("Class {} {}. Given {} from event type {}"
                        "".format(cls, e, event.__dict__, type(event)))
    if isinstance(obj, VersionedEntity):
        obj._increment_version()
    return obj


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


class AbstractEventPlayer(with_metaclass(ABCMeta)):
    pass


class AbstractEntityRepository(AbstractEventPlayer):
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
