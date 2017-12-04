"""
The entity module provides base classes for domain entities.
"""
from abc import ABCMeta, abstractmethod
from uuid import uuid4

from six import with_metaclass

from eventsourcing.domain.model.events import AttributeChanged, Created, Discarded, DomainEvent, \
    EventWithOriginatorID, \
    EventWithOriginatorVersion, EventWithTimestamp, GENESIS_HASH, QualnameABC, publish
from eventsourcing.exceptions import EntityIsDiscarded, EventHashError, HeadHashError, OriginatorIDError, \
    OriginatorVersionError
from eventsourcing.utils.time import timestamp_from_uuid
from eventsourcing.utils.topic import get_topic, resolve_topic


class DomainEntity(QualnameABC):
    __with_data_integrity__ = True  # set False to fall back to v3.x behaviour
    __genesis_hash__ = GENESIS_HASH

    """Base class for domain entities."""
    def __init__(self, id):
        self._id = id
        self.__is_discarded__ = False
        if self.__with_data_integrity__:
            self.__head__ = type(self).__genesis_hash__

    def __eq__(self, other):
        return type(self) == type(other) and self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)

    __hash__ = None  # For Python 2.7, so hash(obj) raises TypeError.

    @property
    def id(self):
        return self._id

    class Event(EventWithOriginatorID, DomainEvent):
        """
        Supertype for events of domain entities.
        """
        __with_data_integrity__ = True  # set False to fall back to v3.x behaviour

        def __init__(self, **kwargs):
            super(DomainEntity.Event, self).__init__(**kwargs)
            if self.__with_data_integrity__:
                assert '__event_hash__' not in self.__dict__
                self.__dict__['__event_hash__'] = self.hash(self.__dict__)

        def __hash__(self):
            """
            Computes a Python integer hash for an event, using its event hash string.
            """
            if '__event_hash__' in self.__dict__:
                return hash((self.__event_hash__, type(self)))
            else:
                return hash(super(DomainEntity.Event, self).__hash__())

        @property
        def __event_hash__(self):
            return self.__dict__.get('__event_hash__')

        def mutate(self, obj):
            """
            Update obj with values from self.

            Can be extended, but subclasses must call super
            method, and return an object.

            :param obj: object to be mutated
            :return: mutated object
            """
            if self.__with_data_integrity__:
                self.__check_event_hash__()
            self.__check_obj__(obj)
            if getattr(type(obj), '__with_data_integrity__', True):
                obj.__head__ = self.__event_hash__
            self._mutate(obj)
            return obj

        def __check_event_hash__(self):
            state = self.__dict__.copy()
            event_hash = state.pop('__event_hash__')
            if event_hash != self.hash(state):
                raise EventHashError()

        def __check_obj__(self, obj):
            """
            Checks the event's originator ID matches the target's ID.
            """
            # Check event's originator ID matches the obj ID.
            if self.originator_id != obj._id:
                raise OriginatorIDError(
                    "'{}' not equal to event originator ID '{}'"
                    "".format(obj.id, self.originator_id)
                )
            # Checks obj __head__ matches the event's previous hash.
            if getattr(type(obj), '__with_data_integrity__', True):
                if self.__previous_hash__ != obj.__head__:
                    raise HeadHashError(obj.id, obj.__head__, type(self))

        def _mutate(self, obj):
            """
            Private "helper" for use in custom models, to
            update obj with values from self without needing
            to call super method and return obj.

            Can be overridden by subclasses. Should not return
            a value. Values returned by this method are ignored.

            Please note, subclasses that extend mutate() might
            not have fully completed that method before this method
            is called. To ensure all base classes have completed
            their mutate behaviour before mutating an event in a concrete
            class, extend mutate() instead of overriding this method.

            :param obj: object to be mutated
            """

    @classmethod
    def create(cls, originator_id=None, **kwargs):
        if originator_id is None:
            originator_id = uuid4()
        if getattr(cls, '__with_data_integrity__', True):
            genesis_hash = getattr(cls, '__genesis_hash__', GENESIS_HASH)
            kwargs['__previous_hash__'] = genesis_hash
        event = cls.Created(
            originator_id=originator_id,
            originator_topic=get_topic(cls),
            **kwargs
        )
        obj = event.mutate()
        obj.__publish__(event)
        return obj

    class Created(Event, Created):
        """
        Published when an entity is created.
        """
        def __init__(self, originator_topic, **kwargs):
            super(DomainEntity.Created, self).__init__(
                originator_topic=originator_topic,
                **kwargs
            )

        @property
        def originator_topic(self):
            return self.__dict__['originator_topic']

        def mutate(self, cls=None):
            if cls is None:
                cls = resolve_topic(self.originator_topic)
            with_data_integrity = getattr(cls, '__with_data_integrity__', True)
            if with_data_integrity:
                self.__check_event_hash__()
            obj = cls(**self._get_constructor_kwargs())
            if with_data_integrity:
                obj.__head__ = self.__event_hash__
            return obj

        def _get_constructor_kwargs(self):
            kwargs = self.__dict__.copy()
            kwargs['id'] = kwargs.pop('originator_id')
            kwargs.pop('originator_topic', None)
            kwargs.pop('__event_hash__', None)
            kwargs.pop('__previous_hash__', None)
            kwargs.pop('__topic__', None)
            return kwargs

    def __change_attribute__(self, name, value):
        """
        Changes named attribute with the given value,
        by triggering an AttributeChanged event.
        """
        self.__trigger_event__(self.AttributeChanged, name=name, value=value)

    class AttributeChanged(Event, AttributeChanged):
        """
        Published when a DomainEntity is discarded.
        """
        def mutate(self, obj):
            obj = super(DomainEntity.AttributeChanged, self).mutate(obj)
            setattr(obj, self.name, self.value)
            return obj

    def __discard__(self):
        """
        Discards self, by triggering a Discarded event.
        """
        self.__trigger_event__(self.Discarded)

    class Discarded(Discarded, Event):
        """
        Published when a DomainEntity is discarded.
        """
        def mutate(self, obj):
            obj = super(DomainEntity.Discarded, self).mutate(obj)
            obj.__is_discarded__ = True
            return None

    def __assert_not_discarded__(self):
        """
        Raises exception if entity has been discarded already.
        """
        if self.__is_discarded__:
            raise EntityIsDiscarded("Entity is discarded")

    def __trigger_event__(self, event_class, **kwargs):
        """
        Constructs, applies, and publishes a domain event.
        """
        self.__assert_not_discarded__()
        if type(self).__with_data_integrity__:
            kwargs['__previous_hash__'] = self.__head__
        event = event_class(
            originator_id=self._id,
            **kwargs
        )
        event.mutate(self)
        self.__publish__(event)

    def __publish__(self, event):
        """
        Publishes given event for subscribers in the application.

        :param event: domain event or list of events
        """
        self.__publish_to_subscribers__(event)

    def __publish_to_subscribers__(self, event):
        """
        Actually dispatches given event to publish-subscribe mechanism.

        :param event: domain event or list of events
        """
        publish(event)


class VersionedEntity(DomainEntity):
    def __init__(self, __version__=None, **kwargs):
        super(VersionedEntity, self).__init__(**kwargs)
        self.___version__ = __version__

    @property
    def __version__(self):
        return self.___version__

    def __trigger_event__(self, event_class, **kwargs):
        """
        Triggers domain event with entity's next version number.
        """
        return super(VersionedEntity, self).__trigger_event__(
            event_class=event_class,
            originator_version = self.__version__ + 1,
            **kwargs
        )

    class Event(EventWithOriginatorVersion, DomainEntity.Event):
        """Supertype for events of versioned entities."""
        def mutate(self, obj):
            obj = super(VersionedEntity.Event, self).mutate(obj)
            if obj is not None:
                obj.___version__ = self.originator_version
            return obj

        def __check_obj__(self, obj):
            """
            Also checks the event's originator version follows this entity's version.
            """
            super(VersionedEntity.Event, self).__check_obj__(obj)
            if obj.__version__ + 1 != self.originator_version:
                raise OriginatorVersionError(
                    ("Event originated from entity at version {}, "
                     "but entity is currently at version {}. "
                     "Event type: '{}', entity type: '{}', entity ID: '{}'"
                     "".format(self.originator_version, obj.__version__,
                               type(self).__name__, type(obj).__name__, obj._id)
                     )
                )

    class Created(DomainEntity.Created, Event):
        """Published when a VersionedEntity is created."""
        def __init__(self, originator_version=0, **kwargs):
            super(VersionedEntity.Created, self).__init__(originator_version=originator_version, **kwargs)

        def _get_constructor_kwargs(self):
            kwargs = super(VersionedEntity.Created, self)._get_constructor_kwargs()
            kwargs['__version__'] = kwargs.pop('originator_version')
            return kwargs

    class AttributeChanged(Event, DomainEntity.AttributeChanged):
        """Published when a VersionedEntity is changed."""

    class Discarded(Event, DomainEntity.Discarded):
        """Published when a VersionedEntity is discarded."""


class TimestampedEntity(DomainEntity):
    def __init__(self, __created_on__, **kwargs):
        super(TimestampedEntity, self).__init__(**kwargs)
        self.___created_on__ = __created_on__
        self.___last_modified__ = __created_on__

    @property
    def __created_on__(self):
        return self.___created_on__

    @property
    def __last_modified__(self):
        return self.___last_modified__

    class Event(DomainEntity.Event, EventWithTimestamp):
        """Supertype for events of timestamped entities."""
        def mutate(self, obj):
            """Update obj with values from self."""
            obj = super(TimestampedEntity.Event, self).mutate(obj)
            if obj is not None:
                assert isinstance(obj, TimestampedEntity), obj
                obj.___last_modified__ = self.timestamp
            return obj

    class Created(DomainEntity.Created, Event):
        """Published when a TimestampedEntity is created."""
        def _get_constructor_kwargs(self):
            kwargs = super(TimestampedEntity.Created, self)._get_constructor_kwargs()
            kwargs['__created_on__'] = kwargs.pop('timestamp')
            return kwargs



    class AttributeChanged(Event, DomainEntity.AttributeChanged):
        """Published when a TimestampedEntity is changed."""

    class Discarded(Event, DomainEntity.Discarded):
        """Published when a TimestampedEntity is discarded."""


class TimeuuidedEntity(DomainEntity):
    def __init__(self, event_id, **kwargs):
        super(TimeuuidedEntity, self).__init__(**kwargs)
        self._initial_event_id = event_id
        self._last_event_id = event_id

    @property
    def __created_on__(self):
        return timestamp_from_uuid(self._initial_event_id)

    @property
    def __last_modified__(self):
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


class AbstractEventPlayer(with_metaclass(ABCMeta)):
    pass


class AbstractEntityRepository(AbstractEventPlayer):
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

    @abstractmethod
    def get_entity(self, entity_id):
        """
        Returns entity for given ID.
        """

    @property
    @abstractmethod
    def event_store(self):
        """
        Returns event store object used by this repository.
        """
