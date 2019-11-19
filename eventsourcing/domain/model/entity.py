from decimal import Decimal
from typing import Any, Callable, Dict, Optional, Type, cast
from uuid import UUID, uuid4

import eventsourcing.domain.model.events as events
from eventsourcing.domain.model.decorators import subclassevents
from eventsourcing.domain.model.events import (
    DomainEvent,
    EventWithHash,
    EventWithOriginatorID,
    EventWithOriginatorVersion,
    EventWithTimestamp,
    GENESIS_HASH,
    publish,
)
from eventsourcing.exceptions import (
    EntityIsDiscarded,
    HeadHashError,
    OriginatorIDError,
    OriginatorVersionError,
)
from eventsourcing.types import (
    AbstractDomainEntity,
    AbstractDomainEvent,
    MetaAbstractDomainEntity,
    T_en,
    T_ev,
    T_ev_evs,
)
from eventsourcing.utils.times import decimaltimestamp_from_uuid
from eventsourcing.utils.topic import get_topic, resolve_topic


class MetaDomainEntity(MetaAbstractDomainEntity):
    __subclassevents__ = False

    # Todo: Delete the '**kwargs' when library no longer supports Python3.6.
    #  - When we started using typing.Generic, we started getting
    #    an error in 3.6 (only) "unexpected keyword argument 'tvars'"
    #    which was cured by adding **kwargs here. It's not needed
    #    for Python3.7, and only supports backward compatibility.
    #    So it can be removed when support for Python 3.6 dropped.
    def __init__(cls, name, bases, attrs, **_):
        super().__init__(name, bases, attrs)
        if name == "_gorg":
            # Todo: Also Remove this block when dropping support for Python 3.6.
            # Needed in 3.6 only, stops infinite recursion between typing and abc
            # doing subclass checks. Don't know why. Seems issue fixed in Python 3.7.
            pass
        elif cls.__subclassevents__ is True:
            # Define (or redefined) subclass domain events.
            # print("Subclssing events on:", cls)
            subclassevents(cls)


class DomainEntity(AbstractDomainEntity[T_ev], metaclass=MetaDomainEntity):
    """
    Supertype for domain model entity.
    """

    __subclassevents__ = False

    class Event(EventWithOriginatorID[T_en], DomainEvent[T_en]):
        """
        Supertype for events of domain model entities.
        """

        def __check_obj__(self, obj: T_en) -> None:
            """
            Checks state of obj before mutating.

            :param obj: Domain entity to be checked.

            :raises OriginatorIDError: if the originator_id is mismatched
            """
            # Check ID matches originator ID.
            entity = cast(DomainEntity, obj)
            if entity.id != self.originator_id:
                raise OriginatorIDError(
                    "'{}' not equal to event originator ID '{}'"
                    "".format(entity.id, self.originator_id)
                )

    @classmethod
    def __create__(
        cls: Type[T_en],
        originator_id: Optional[UUID] = None,
        event_class: Optional[Type[T_ev]] = None,
        **kwargs
    ) -> T_en:
        """
        Creates a new domain entity.

        Constructs a "created" event, constructs the entity object
        from the event, publishes the "created" event, and returns
        the new domain entity object.

        :param originator_id: ID of the new domain entity (defaults to ``uuid4()``).
        :param event_class: Domain event class to be used for the "created" event.
        :param kwargs: Other named attribute values of the "created" event.
        :return: New domain entity object.
        :rtype: DomainEntity
        """
        if originator_id is None:
            originator_id = uuid4()
        event: AbstractDomainEvent = (event_class or cls.Created)(
            originator_id=originator_id, originator_topic=get_topic(cls), **kwargs
        )
        obj = event.__mutate__(None)
        assert obj is not None, "{} returned None".format(
            type(event).__mutate__.__qualname__
        )
        obj.__publish__(event)
        return obj

    class Created(Event, events.Created[T_en]):
        """
        Triggered when an entity is created.
        """

        def __init__(self, originator_topic: str, **kwargs):
            super(DomainEntity.Created, self).__init__(
                originator_topic=originator_topic, **kwargs
            )

        @property
        def originator_topic(self) -> str:
            """
            Topic (a string) representing the class of the originating domain entity.

            :rtype: str
            """
            return self.__dict__["originator_topic"]

        def __mutate__(self, obj: Optional[T_en]) -> Optional[T_en]:
            """
            Constructs object from an entity class,
            which is obtained by resolving the originator topic,
            unless it is given as method argument ``entity_class``.

            :param entity_class: Class of domain entity to be constructed.
            """
            entity_class: Callable
            if obj is None:
                entity_class = resolve_topic(self.originator_topic)
            else:
                entity_class = cast(MetaDomainEntity, obj)
            return entity_class(**self.__entity_kwargs__)

        @property
        def __entity_kwargs__(self) -> Dict[str, Any]:
            kwargs = self.__dict__.copy()
            kwargs["id"] = kwargs.pop("originator_id")
            kwargs.pop("originator_topic", None)
            kwargs.pop("__event_topic__", None)
            return kwargs

    def __init__(self, id):
        self._id = id
        self.__is_discarded__ = False

    @property
    def id(self) -> UUID:
        """The immutable ID of the domain entity.

        This value is set using the ``originator_id`` of the
        "created" event constructed by ``__create__()``.

        An entity ID allows an instance to be
        referenced and distinguished from others, even
        though its state may change over time.

        This attribute has the normal "public" format for a Python object
        attribute name, because by definition all domain entities have an ID.
        """
        return self._id

    def __change_attribute__(self: "DomainEntity", name: str, value: Any) -> None:
        """
        Changes named attribute with the given value,
        by triggering an AttributeChanged event.
        """
        event_class = self.AttributeChanged
        self.__trigger_event__(event_class=event_class, name=name, value=value)

    class AttributeChanged(Event, events.AttributeChanged[T_en]):
        """
        Triggered when a named attribute is assigned a new value.
        """

        def __mutate__(self, obj: Optional[T_en]) -> Optional[T_en]:
            obj = super(DomainEntity.AttributeChanged, self).__mutate__(obj)
            setattr(obj, self.name, self.value)
            return obj

    def __discard__(self):
        """
        Discards self, by triggering a Discarded event.
        """
        self.__trigger_event__(self.Discarded)

    class Discarded(events.Discarded[T_en], Event):
        """
        Triggered when a DomainEntity is discarded.
        """

        def __mutate__(self, obj: Optional[T_en]) -> Optional[T_en]:
            obj = super(DomainEntity.Discarded, self).__mutate__(obj)
            entity = cast(DomainEntity, obj)
            entity.__is_discarded__ = True
            return None

    def __assert_not_discarded__(self):
        """
        Asserts that this entity has not been discarded.

        Raises EntityIsDiscarded exception if entity has been discarded already.
        """
        if self.__is_discarded__:
            raise EntityIsDiscarded("Entity is discarded")

    def __trigger_event__(self, event_class: Type[T_ev], **kwargs) -> None:
        """
        Constructs, applies, and publishes a domain event.
        """
        self.__assert_not_discarded__()
        event: T_ev = event_class(originator_id=self.id, **kwargs)
        self.__mutate__(event)
        self.__publish__(event)

    def __mutate__(self, event: T_ev):
        """
        Mutates this entity with the given event.

        This method calls on the event object to mutate this
        entity, because the mutation behaviour of different types
        of events was usefully factored onto the event classes, and
        the event mutate() method is the most convenient way to
        defined behaviour in domain models.

        However, as an alternative to implementing the mutate()
        method on domain model events, this method can be extended
        with a method that is capable of mutating an entity for all
        the domain event classes introduced by the entity class.

        Similarly, this method can be overridden entirely in subclasses,
        so long as all of the mutation behaviour is implemented in the
        mutator function, including the mutation behaviour of the events
        defined on the library event classes that would no longer be invoked.

        However, if the entity class defines a mutator function, or if a
        separate mutator function is used, then it must be involved in
        the event sourced repository used to replay events, which by default
        knows nothing about the domain entity class. In practice, this
        means having a repository for each kind of entity, rather than
        the application just having one repository, with each repository
        having a mutator function that can project the entity events
        into an entity.
        """
        event.__mutate__(self)

    def __publish__(self, event: T_ev_evs):
        """
        Publishes given event for subscribers in the application.

        :param event: domain event or list of events
        """
        self.__publish_to_subscribers__(event)

    def __publish_to_subscribers__(self, event: T_ev_evs):
        """
        Actually dispatches given event to publish-subscribe mechanism.

        :param event: domain event or list of events
        """
        publish(event)

    def __eq__(self, other):
        return type(self) == type(other) and self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)


class EntityWithHashchain(DomainEntity[T_ev]):
    __genesis_hash__ = GENESIS_HASH

    def __init__(self, *args, **kwargs):
        super(EntityWithHashchain, self).__init__(*args, **kwargs)
        self.__head__: str = type(self).__genesis_hash__

    class Event(EventWithHash[T_en], DomainEntity.Event[T_en]):
        """
        Supertype for events of domain entities.
        """

        def __mutate__(self, obj: Optional[T_en]) -> Optional[T_en]:
            # Call super method.
            obj = super(EntityWithHashchain.Event, self).__mutate__(obj)

            # Set entity head from event hash.
            #  - unless just discarded...
            if obj is not None:
                entity = cast(EntityWithHashchain, obj)
                entity.__head__ = self.__event_hash__

            return obj

        def __check_obj__(self, obj: T_en) -> None:
            """
            Extends superclass method by checking the __previous_hash__
            of this event matches the __head__ hash of the entity obj.
            """
            # Call super method.
            super(EntityWithHashchain.Event, self).__check_obj__(obj)

            # Check __head__ matches previous hash.
            entity = cast(EntityWithHashchain, obj)
            if entity.__head__ != self.__dict__.get("__previous_hash__"):
                raise HeadHashError(entity.id, entity.__head__, type(self))

    class Created(Event[T_en], DomainEntity.Created[T_en]):
        @property
        def __entity_kwargs__(self) -> Dict[str, Any]:
            # Get super property.
            kwargs = super(EntityWithHashchain.Created, self).__entity_kwargs__

            # Drop the event hashes.
            kwargs.pop("__event_hash__", None)
            kwargs.pop("__previous_hash__", None)

            return kwargs

        def __mutate__(self, obj: Optional[T_en]) -> Optional[T_en]:
            # Call super method.
            return super(EntityWithHashchain.Created, self).__mutate__(obj)

    class AttributeChanged(Event, DomainEntity.AttributeChanged[T_en]):
        pass

    class Discarded(Event[T_en], DomainEntity.Discarded[T_en]):
        def __mutate__(self, obj: Optional[T_en]) -> Optional[T_en]:
            # Set entity head from event hash.
            entity = cast(EntityWithHashchain, obj)
            entity.__head__ = self.__event_hash__

            # Call super method.
            return super(EntityWithHashchain.Discarded, self).__mutate__(obj)

    @classmethod
    def __create__(cls: Type[T_en], *args, **kwargs) -> T_en:
        # Insert a "genesis hash" as __previous_hash__ in initial event.
        kwargs["__previous_hash__"] = getattr(cls, "__genesis_hash__", GENESIS_HASH)
        return super(EntityWithHashchain, cls).__create__(*args, **kwargs)

    def __trigger_event__(self, event_class: Type[T_ev], **kwargs) -> None:
        assert isinstance(event_class, type), type(event_class)
        kwargs["__previous_hash__"] = self.__head__
        super(EntityWithHashchain, self).__trigger_event__(event_class, **kwargs)


class VersionedEntity(DomainEntity[T_ev]):
    def __init__(self, __version__: int, **kwargs):
        super().__init__(**kwargs)
        self.___version__: int = __version__

    @property
    def __version__(self) -> int:
        return self.___version__

    def __trigger_event__(self, event_class: Type[T_ev], **kwargs) -> None:
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
            event_class=event_class, originator_version=self.__version__ + 1, **kwargs
        )

    class Event(EventWithOriginatorVersion[T_en], DomainEntity.Event[T_en]):
        """Supertype for events of versioned entities."""

        def __mutate__(self, obj: Optional[T_en]) -> Optional[T_en]:
            obj = super(VersionedEntity.Event, self).__mutate__(obj)
            if obj is not None:
                entity = cast(EventWithOriginatorVersion, obj)
                entity.___version__ = self.originator_version
            return obj

        def __check_obj__(self, obj: T_en) -> None:
            """
            Extends superclass method by checking the event's
            originator version follows (1 +) this entity's version.
            """
            super(VersionedEntity.Event, self).__check_obj__(obj)
            entity = cast(VersionedEntity, obj)
            if self.originator_version != entity.__version__ + 1:
                raise OriginatorVersionError(
                    (
                        "Event takes entity to version {}, "
                        "but entity is currently at version {}. "
                        "Event type: '{}', entity type: '{}', entity ID: '{}'"
                        "".format(
                            self.originator_version,
                            entity.__version__,
                            type(self).__name__,
                            type(entity).__name__,
                            entity._id,
                        )
                    )
                )

    class Created(DomainEntity.Created[T_en], Event[T_en]):
        """Published when a VersionedEntity is created."""

        def __init__(self, originator_version=0, *args, **kwargs):
            super(VersionedEntity.Created, self).__init__(
                originator_version=originator_version, *args, **kwargs
            )

        @property
        def __entity_kwargs__(self) -> Dict[str, Any]:
            # Get super property.
            kwargs = super(VersionedEntity.Created, self).__entity_kwargs__
            kwargs["__version__"] = kwargs.pop("originator_version")
            return kwargs

    class AttributeChanged(Event[T_en], DomainEntity.AttributeChanged[T_en]):
        """Published when a VersionedEntity is changed."""

    class Discarded(Event[T_en], DomainEntity.Discarded[T_en]):
        """Published when a VersionedEntity is discarded."""


class TimestampedEntity(DomainEntity[T_ev]):
    def __init__(self, __created_on__: Decimal, **kwargs):
        super(TimestampedEntity, self).__init__(**kwargs)
        self.___created_on__ = __created_on__
        self.___last_modified__ = __created_on__

    @property
    def __created_on__(self) -> Decimal:
        return self.___created_on__

    @property
    def __last_modified__(self) -> Decimal:
        return self.___last_modified__

    class Event(DomainEntity.Event[T_en], EventWithTimestamp[T_en]):
        """Supertype for events of timestamped entities."""

        def __mutate__(self, obj: Optional[T_en]) -> Optional[T_en]:
            """Updates 'obj' with values from self."""
            obj = super(TimestampedEntity.Event, self).__mutate__(obj)
            if obj is not None:
                entity = cast(TimestampedEntity, obj)
                entity.___last_modified__ = self.timestamp
            return obj

    class Created(DomainEntity.Created[T_en], Event[T_en]):
        """Published when a TimestampedEntity is created."""

        @property
        def __entity_kwargs__(self) -> Dict[str, Any]:
            # Get super property.
            kwargs = super(TimestampedEntity.Created, self).__entity_kwargs__
            kwargs["__created_on__"] = kwargs.pop("timestamp")
            return kwargs

    class AttributeChanged(Event[T_en], DomainEntity.AttributeChanged[T_en]):
        """Published when a TimestampedEntity is changed."""

    class Discarded(Event[T_en], DomainEntity.Discarded[T_en]):
        """Published when a TimestampedEntity is discarded."""


# Todo: Move stuff from "test_customise_with_alternative_domain_event_type" in here (
#  to define event classes
#  and update ___last_event_id__ in mutate method).


class TimeuuidedEntity(DomainEntity[T_ev]):
    def __init__(self, event_id, **kwargs):
        super(TimeuuidedEntity, self).__init__(**kwargs)
        self.___initial_event_id__ = event_id
        self.___last_event_id__ = event_id

    @property
    def __created_on__(self) -> Decimal:
        return decimaltimestamp_from_uuid(self.___initial_event_id__)

    @property
    def __last_modified__(self) -> Decimal:
        return decimaltimestamp_from_uuid(self.___last_event_id__)


class TimestampedVersionedEntity(TimestampedEntity[T_ev], VersionedEntity[T_ev]):
    class Event(TimestampedEntity.Event[T_en], VersionedEntity.Event[T_en]):
        """Supertype for events of timestamped, versioned entities."""

    class Created(
        TimestampedEntity.Created[T_en], VersionedEntity.Created, Event[T_en]
    ):
        """Published when a TimestampedVersionedEntity is created."""

    class AttributeChanged(
        Event[T_en],
        TimestampedEntity.AttributeChanged[T_en],
        VersionedEntity.AttributeChanged[T_en],
    ):
        """Published when a TimestampedVersionedEntity is created."""

    class Discarded(
        Event[T_en], TimestampedEntity.Discarded[T_en], VersionedEntity.Discarded[T_en]
    ):
        """Published when a TimestampedVersionedEntity is discarded."""


class TimeuuidedVersionedEntity(TimeuuidedEntity[T_ev], VersionedEntity[T_ev]):
    pass
