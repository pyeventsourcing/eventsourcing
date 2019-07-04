"""
The entity module provides base classes for domain entities.
"""
from abc import abstractmethod
from uuid import uuid4

from eventsourcing.domain.model.events import AttributeChanged, Created, Discarded, DomainEvent, EventWithHash, \
    EventWithOriginatorID, EventWithOriginatorVersion, EventWithTimestamp, GENESIS_HASH, publish
from eventsourcing.exceptions import EntityIsDiscarded, HeadHashError, OriginatorIDError, OriginatorVersionError
from eventsourcing.utils.times import decimaltimestamp_from_uuid
from eventsourcing.utils.topic import get_topic, resolve_topic


class DomainEntity(object):
    """
    Base class for domain entities.
    """

    def __init__(self, id):
        self._id = id
        self.__is_discarded__ = False

    @property
    def id(self):
        """Entity ID allows an entity instance to be
        referenced and distinguished from others, even
        though its state may change over time.
        """
        return self._id

    class Event(EventWithOriginatorID, DomainEvent):
        """
        Supertype for events of domain entities.
        """

        def __mutate__(self, obj):
            # Call super method.
            return super(DomainEntity.Event, self).__mutate__(obj)

        def __check_obj__(self, obj):
            """
            Checks obj state before mutating.
            """
            # Check obj is not None.
            assert obj is not None, "'obj' is None"

            # Check ID matches originator ID.
            if obj.id != self.originator_id:
                raise OriginatorIDError(
                    "'{}' not equal to event originator ID '{}'"
                    "".format(obj.id, self.originator_id)
                )

    @classmethod
    def __create__(cls, originator_id=None, event_class=None, **kwargs):
        if originator_id is None:
            originator_id = uuid4()
        event = (event_class or cls.Created)(
            originator_id=originator_id,
            originator_topic=get_topic(cls),
            **kwargs
        )
        obj = event.__mutate__()
        obj.__publish__(event)
        return obj

    class Created(Event, Created):
        """
        Triggered when an entity is created.
        """

        def __init__(self, originator_topic, **kwargs):
            super(DomainEntity.Created, self).__init__(
                originator_topic=originator_topic,
                **kwargs
            )

        @property
        def originator_topic(self):
            return self.__dict__['originator_topic']

        def __mutate__(self, entity_class=None):
            if entity_class is None:
                entity_class = resolve_topic(self.originator_topic)
            return entity_class(**self.__entity_kwargs__)

        @property
        def __entity_kwargs__(self):
            kwargs = self.__dict__.copy()
            kwargs['id'] = kwargs.pop('originator_id')
            kwargs.pop('originator_topic', None)
            kwargs.pop('__event_topic__', None)
            return kwargs

    def __change_attribute__(self, name, value):
        """
        Changes named attribute with the given value,
        by triggering an AttributeChanged event.
        """
        self.__trigger_event__(self.AttributeChanged, name=name, value=value)

    class AttributeChanged(Event, AttributeChanged):
        """
        Triggered when a named attribute is assigned a new value.
        """

        def __mutate__(self, obj):
            obj = super(DomainEntity.AttributeChanged, self).__mutate__(obj)
            setattr(obj, self.name, self.value)
            return obj

    def __discard__(self):
        """
        Discards self, by triggering a Discarded event.
        """
        self.__trigger_event__(self.Discarded)

    class Discarded(Discarded, Event):
        """
        Triggered when a DomainEntity is discarded.
        """

        def __mutate__(self, obj):
            obj = super(DomainEntity.Discarded, self).__mutate__(obj)
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
        event = event_class(
            originator_id=self._id,
            **kwargs
        )
        event.__mutate__(self)
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

    __hash__ = None  # For Python 2.7, so hash(obj) raises TypeError.

    def __eq__(self, other):
        return type(self) == type(other) and self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)


class EntityWithHashchain(DomainEntity):
    __genesis_hash__ = GENESIS_HASH

    def __init__(self, *args, **kwargs):
        super(EntityWithHashchain, self).__init__(*args, **kwargs)
        self.__head__ = type(self).__genesis_hash__

    class Event(EventWithHash, DomainEntity.Event):
        """
        Supertype for events of domain entities.
        """

        def __mutate__(self, obj):

            # Call super method.
            obj = super(EntityWithHashchain.Event, self).__mutate__(obj)

            # Set entity head from event hash.
            #  - unless just discarded...
            if obj is not None:
                obj.__head__ = self.__event_hash__

            return obj

        def __check_obj__(self, obj):
            """
            Extends superclass method by checking the __previous_hash__
            of this event matches the __head__ hash of the entity obj.
            """
            # Call super method.
            super(EntityWithHashchain.Event, self).__check_obj__(obj)

            # Check __head__ matches previous hash.
            if obj.__head__ != self.__dict__.get('__previous_hash__'):
                raise HeadHashError(obj.id, obj.__head__, type(self))

    class Created(Event, DomainEntity.Created):
        @property
        def __entity_kwargs__(self):
            # Call super method.
            kwargs = super(EntityWithHashchain.Created, self).__entity_kwargs__

            # Drop the event hashes.
            kwargs.pop('__event_hash__', None)
            kwargs.pop('__previous_hash__', None)

            return kwargs

        def __mutate__(self, entity_class=None):
            # Call super method.
            return super(EntityWithHashchain.Created, self).__mutate__(entity_class)

    class AttributeChanged(Event, DomainEntity.AttributeChanged):
        pass

    class Discarded(Event, DomainEntity.Discarded):
        def __mutate__(self, obj):
            # Set entity head from event hash.
            obj.__head__ = self.__event_hash__

            # Call super method.
            return super(EntityWithHashchain.Discarded, self).__mutate__(obj)

    @classmethod
    def __create__(cls, *args, **kwargs):
        kwargs['__previous_hash__'] = getattr(cls, '__genesis_hash__', GENESIS_HASH)
        return super(EntityWithHashchain, cls).__create__(*args, **kwargs)

    def __trigger_event__(self, event_class, **kwargs):
        assert isinstance(event_class, type), type(event_class)
        kwargs['__previous_hash__'] = self.__head__
        super(EntityWithHashchain, self).__trigger_event__(event_class, **kwargs)


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

        The event carries the version number that the originator
        will have when the originator is mutated with this event.
        (The event's originator version isn't the version of the
        originator that triggered the event. The Created event has
        version 0, and so a newly created instance is at version 0.
        The second event has originator version 1, and so will the
        originator when the second event has been applied.)
        """
        return super(VersionedEntity, self).__trigger_event__(
            event_class=event_class,
            originator_version=self.__version__ + 1,
            **kwargs
        )

    class Event(EventWithOriginatorVersion, DomainEntity.Event):
        """Supertype for events of versioned entities."""

        def __mutate__(self, obj):
            obj = super(VersionedEntity.Event, self).__mutate__(obj)
            if obj is not None:
                obj.___version__ = self.originator_version
            return obj

        def __check_obj__(self, obj):
            """
            Extends superclass method by checking the event's
            originator version follows (1 +) this entity's version.
            """
            super(VersionedEntity.Event, self).__check_obj__(obj)
            if self.originator_version != obj.__version__ + 1:
                raise OriginatorVersionError(
                    ("Event takes entity to version {}, "
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

        @property
        def __entity_kwargs__(self):
            kwargs = super(VersionedEntity.Created, self).__entity_kwargs__
            kwargs['__version__'] = kwargs.pop('originator_version')
            return kwargs

    class AttributeChanged(Event, DomainEntity.AttributeChanged):
        """Published when a VersionedEntity is changed."""

    class Discarded(Event, DomainEntity.Discarded):
        """Published when a VersionedEntity is discarded."""


class TimestampedEntity(DomainEntity):
    def __init__(self, __created_on__=None, **kwargs):
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

        def __mutate__(self, obj):
            """Updates 'obj' with values from self."""
            obj = super(TimestampedEntity.Event, self).__mutate__(obj)
            if obj is not None:
                assert isinstance(obj, TimestampedEntity), obj
                obj.___last_modified__ = self.timestamp
            return obj

    class Created(DomainEntity.Created, Event):
        """Published when a TimestampedEntity is created."""

        @property
        def __entity_kwargs__(self):
            kwargs = super(TimestampedEntity.Created, self).__entity_kwargs__
            kwargs['__created_on__'] = kwargs.pop('timestamp')
            return kwargs

    class AttributeChanged(Event, DomainEntity.AttributeChanged):
        """Published when a TimestampedEntity is changed."""

    class Discarded(Event, DomainEntity.Discarded):
        """Published when a TimestampedEntity is discarded."""


# Todo: Move stuff from "test_customise_with_alternative_domain_event_type" in here (to define event classes
#  and update ___last_event_id__ in mutate method).
class TimeuuidedEntity(DomainEntity):
    def __init__(self, event_id, **kwargs):
        super(TimeuuidedEntity, self).__init__(**kwargs)
        self.___initial_event_id__ = event_id
        self.___last_event_id__ = event_id

    @property
    def __created_on__(self):
        return decimaltimestamp_from_uuid(self.___initial_event_id__)

    @property
    def __last_modified__(self):
        return decimaltimestamp_from_uuid(self.___last_event_id__)


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


class AbstractEventPlayer(object):
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
    def get_entity(self, entity_id, at=None):
        """
        Returns entity for given ID.
        """

    @property
    @abstractmethod
    def event_store(self):
        """
        Returns event store object used by this repository.
        """

    @abstractmethod
    def take_snapshot(self, entity_id, lt=None, lte=None):
        """
        Takes snapshot of entity state, using stored events.
        :return: Snapshot
        """
