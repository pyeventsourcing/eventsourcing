import os
from abc import ABCMeta
from decimal import Decimal
from typing import Any, Dict, Optional, Sequence, Type, TypeVar
from uuid import UUID, uuid4

from eventsourcing.domain.model.decorators import subclassevents
from eventsourcing.domain.model.events import (
    AttributeChangedEvent,
    CreatedEvent,
    DiscardedEvent,
    DomainEvent,
    EventWithHash,
    EventWithOriginatorID,
    EventWithOriginatorVersion,
    EventWithTimestamp,
    publish,
)
from eventsourcing.domain.model.versioning import Upcastable
from eventsourcing.exceptions import (
    EntityIsDiscarded,
    HeadHashError,
    OriginatorIDError,
    OriginatorVersionError,
)
from eventsourcing.utils.times import decimaltimestamp_from_uuid
from eventsourcing.utils.topic import get_topic, resolve_topic
from eventsourcing.whitehead import EnduringObject

# Need to deal with the fact that Python3.6 had GenericMeta.
# Todo: Delete this try/except when dropping support for Python 3.6.
try:
    from typing import GenericMeta

    ABCMeta = GenericMeta  # type: ignore

except ImportError:
    pass


class MetaDomainEntity(ABCMeta):
    __subclassevents__ = False

    # Todo: Delete the '**kwargs' when library no longer supports Python3.6.
    #  - When we started using typing.Generic, we started getting
    #    an error in 3.6 (only) "unexpected keyword argument 'tvars'"
    #    which was cured by adding **kwargs here. It's not needed
    #    for Python3.7, and only supports backward compatibility.
    #    So it can be removed when support for Python 3.6 dropped.
    def __init__(cls, name: str, *args: Any, **kwargs: Any) -> None:
        super().__init__(name, *args, **kwargs)
        if name == "_gorg":
            # Todo: Also Remove this block when dropping support for Python 3.6.
            # Needed in 3.6 only, stops infinite recursion between typing and abc
            # doing subclass checks. Don't know why. Seems issue fixed in Python 3.7.
            pass
        elif cls.__subclassevents__ is True:
            # Redefine entity domain events.
            subclassevents(cls)


TDomainEntity = TypeVar("TDomainEntity", bound="DomainEntity")
TDomainEvent = TypeVar("TDomainEvent", bound="DomainEntity.Event")


class DomainEntity(Upcastable, EnduringObject, metaclass=MetaDomainEntity):
    """
    Supertype for domain model entity.
    """

    __subclassevents__ = False

    class Event(EventWithOriginatorID[TDomainEntity]):
        """
        Supertype for events of domain model entities.
        """

        def __check_obj__(self, obj: TDomainEntity) -> None:
            """
            Checks state of obj before mutating.

            :param obj: Domain entity to be checked.

            :raises OriginatorIDError: if the originator_id is mismatched
            """
            assert isinstance(obj, DomainEntity)  # For PyCharm navigation.
            # Assert ID matches originator ID.
            if obj.id != self.originator_id:
                raise OriginatorIDError(
                    "'{}' not equal to event originator ID '{}'"
                    "".format(obj.id, self.originator_id)
                )

    @classmethod
    def __create__(
        cls: Type[TDomainEntity],
        originator_id: Optional[UUID] = None,
        event_class: Optional[Type["DomainEntity.Created[TDomainEntity]"]] = None,
        **kwargs: Any,
    ) -> TDomainEntity:
        """
        Creates a new domain entity.

        Constructs a "created" event, constructs the entity object
        from the event, publishes the "created" event, and returns
        the new domain entity object.

        :param cls DomainEntity: Class of domain event
        :param originator_id: ID of the new domain entity (defaults to ``uuid4()``).
        :param event_class: Domain event class to be used for the "created" event.
        :param kwargs: Other named attribute values of the "created" event.
        :return: New domain entity object.
        :rtype: DomainEntity
        """

        if originator_id is None:
            originator_id = uuid4()

        if event_class is None:
            assert issubclass(cls, DomainEntity)  # For navigation in PyCharm.
            created_event_class: Type[DomainEntity.Created[TDomainEntity]] = cls.Created
        else:
            created_event_class = event_class

        event = created_event_class(
            originator_id=originator_id, originator_topic=get_topic(cls), **kwargs
        )

        obj = event.__mutate__(None)

        assert obj is not None, "{} returned None".format(
            type(event).__mutate__.__qualname__
        )

        obj.__publish__([event])
        return obj

    class Created(CreatedEvent[TDomainEntity], Event[TDomainEntity]):
        """
        Triggered when an entity is created.
        """

        def __init__(self, originator_topic: str, **kwargs: Any):
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

        def __mutate__(self, obj: Optional[TDomainEntity]) -> Optional[TDomainEntity]:
            """
            Constructs object from an entity class,
            which is obtained by resolving the originator topic,
            unless it is given as method argument ``entity_class``.

            :param entity_class: Class of domain entity to be constructed.
            """
            entity_class: Type[TDomainEntity] = resolve_topic(self.originator_topic)
            return entity_class(**self.__entity_kwargs__)

        @property
        def __entity_kwargs__(self) -> Dict[str, Any]:
            kwargs = self.__dict__.copy()
            kwargs["id"] = kwargs.pop("originator_id")
            kwargs.pop("originator_topic", None)
            kwargs.pop("__event_topic__", None)
            kwargs.pop("__event_hash_method_name__", None)
            return kwargs

    def __init__(self, id: UUID):
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

    def __change_attribute__(
        self: TDomainEntity, name: str, value: Any, **kwargs
    ) -> None:
        """
        Changes named attribute with the given value,
        by triggering an AttributeChanged event.
        """
        event_class: Type[
            "DomainEntity.AttributeChanged[TDomainEntity]"
        ] = self.AttributeChanged
        assert isinstance(self, DomainEntity)  # For PyCharm navigation.
        self.__trigger_event__(
            event_class=event_class, name=name, value=value, **kwargs
        )

    class AttributeChanged(Event[TDomainEntity], AttributeChangedEvent[TDomainEntity]):
        """
        Triggered when a named attribute is assigned a new value.
        """

        def __mutate__(self, obj: Optional[TDomainEntity]) -> Optional[TDomainEntity]:
            obj = super(DomainEntity.AttributeChanged, self).__mutate__(obj)
            setattr(obj, self.name, self.value)
            return obj

    def __discard__(self: TDomainEntity, **kwargs) -> None:
        """
        Discards self, by triggering a Discarded event.
        """
        event_class: Type["DomainEntity.Discarded[TDomainEntity]"] = self.Discarded
        assert isinstance(self, DomainEntity)  # For PyCharm navigation.
        self.__trigger_event__(event_class=event_class, **kwargs)

    class Discarded(DiscardedEvent[TDomainEntity], Event[TDomainEntity]):
        """
        Triggered when a DomainEntity is discarded.
        """

        def __mutate__(self, obj: Optional[TDomainEntity]) -> Optional[TDomainEntity]:
            obj = super(DomainEntity.Discarded, self).__mutate__(obj)
            if obj is not None:
                assert isinstance(obj, DomainEntity)  # For PyCharm navigation.
                obj.__is_discarded__ = True
            return None

    def __assert_not_discarded__(self) -> None:
        """
        Asserts that this entity has not been discarded.

        Raises EntityIsDiscarded exception if entity has been discarded already.
        """
        if self.__is_discarded__:
            raise EntityIsDiscarded("Entity is discarded")

    def __trigger_event__(self, event_class: Type[TDomainEvent], **kwargs: Any) -> None:
        """
        Constructs, applies, and publishes a domain event.
        """
        self.__assert_not_discarded__()
        event: TDomainEvent = event_class(originator_id=self.id, **kwargs)
        self.__mutate__(event)
        self.__publish__([event])

    def __mutate__(self, event: TDomainEvent) -> None:
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
        assert isinstance(event, DomainEntity.Event)
        event.__mutate__(self)

    def __publish__(self, event: Sequence[TDomainEvent]) -> None:
        """
        Publishes given event for subscribers in the application.

        :param event: domain event or list of events
        """
        self.__publish_to_subscribers__(event)

    def __publish_to_subscribers__(self, events: Sequence[TDomainEvent]) -> None:
        """
        Actually dispatches given event to publish-subscribe mechanism.

        :param events: list of domain events
        """
        publish(events)

    def __eq__(self, other: object) -> bool:
        return type(self) == type(other) and self.__dict__ == other.__dict__

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)


TEntityWithHashchain = TypeVar("TEntityWithHashchain", bound="EntityWithHashchain")

GENESIS_HASH: str = os.getenv("GENESIS_HASH", "")


class EntityWithHashchain(DomainEntity):
    __genesis_hash__ = GENESIS_HASH

    def __init__(self, *args: Any, **kwargs: Any):
        super(EntityWithHashchain, self).__init__(*args, **kwargs)
        self.__head__: str = type(self).__genesis_hash__

    class Event(
        EventWithHash[TEntityWithHashchain], DomainEntity.Event[TEntityWithHashchain]
    ):
        """
        Supertype for events of domain entities.
        """

        def __mutate__(
            self, obj: Optional[TEntityWithHashchain]
        ) -> Optional[TEntityWithHashchain]:
            # Call super method.
            obj = super(EntityWithHashchain.Event, self).__mutate__(obj)

            # Set entity head from event hash.
            #  - unless just discarded...
            if obj is not None:
                assert isinstance(obj, EntityWithHashchain)
                obj.__head__ = self.__event_hash__

            return obj

        def __check_obj__(self, obj: TEntityWithHashchain) -> None:
            """
            Extends superclass method by checking the __previous_hash__
            of this event matches the __head__ hash of the entity obj.
            """
            # Call super method.
            super(EntityWithHashchain.Event, self).__check_obj__(obj)
            assert isinstance(obj, EntityWithHashchain)  # For PyCharm navigation.
            # Assert __head__ equals __previous_hash__.
            if obj.__head__ != self.__dict__.get("__previous_hash__"):
                raise HeadHashError(obj.id, obj.__head__, type(self))

    class Created(
        Event[TEntityWithHashchain], DomainEntity.Created[TEntityWithHashchain]
    ):
        @property
        def __entity_kwargs__(self) -> Dict[str, Any]:
            # Get super property.
            kwargs = super(EntityWithHashchain.Created, self).__entity_kwargs__

            # Drop the event hashes.
            kwargs.pop("__event_hash__", None)
            kwargs.pop("__previous_hash__", None)

            return kwargs

    class AttributeChanged(
        Event[TEntityWithHashchain], DomainEntity.AttributeChanged[TEntityWithHashchain]
    ):
        pass

    class Discarded(
        Event[TEntityWithHashchain], DomainEntity.Discarded[TEntityWithHashchain]
    ):
        def __mutate__(
            self, obj: Optional[TEntityWithHashchain]
        ) -> Optional[TEntityWithHashchain]:
            # Set entity head from event hash.
            if obj:
                assert isinstance(obj, EntityWithHashchain)  # For PyCharm navigation.
                obj.__head__ = self.__event_hash__

            # Call super method.
            return super(EntityWithHashchain.Discarded, self).__mutate__(obj)

    @classmethod
    def __create__(
        cls: Type[TEntityWithHashchain],
        originator_id: Optional[UUID] = None,
        event_class: Optional[
            Type["DomainEntity.Created[TEntityWithHashchain]"]
        ] = None,
        **kwargs: Any,
    ) -> TEntityWithHashchain:
        # Initialise the hash-chain with "genesis hash".
        kwargs["__previous_hash__"] = getattr(cls, "__genesis_hash__", GENESIS_HASH)
        assert issubclass(cls, EntityWithHashchain)  # For PyCharm navigation.
        obj = super(EntityWithHashchain, cls).__create__(
            originator_id=originator_id, event_class=event_class, **kwargs
        )
        assert isinstance(obj, EntityWithHashchain)  # For PyCharm type checking.
        return obj

    def __trigger_event__(self, event_class: Type[TDomainEvent], **kwargs: Any) -> None:
        kwargs["__previous_hash__"] = self.__head__
        super(EntityWithHashchain, self).__trigger_event__(event_class, **kwargs)


TVersionedEntity = TypeVar("TVersionedEntity", bound="VersionedEntity")
TVersionedEvent = TypeVar("TVersionedEvent", bound="VersionedEntity.Event")


class VersionedEntity(DomainEntity):
    def __init__(self, __version__: int, **kwargs: Any):
        super().__init__(**kwargs)
        self.___version__: int = __version__

    @property
    def __version__(self) -> int:
        return self.___version__

    def __trigger_event__(self, event_class: Type[TDomainEvent], **kwargs: Any) -> None:
        """
        Increments the version number when an event is triggered.

        The event carries the version number that the originator
        will have when the originator is mutated with this event.
        (The event's "originator" version isn't the version of the
        originator before the event was triggered, but represents
        the result of the work of incrementing the version, which
        is then set in the event as normal. The Created event has
        version 0, and a newly created instance is at version 0.
        The second event has originator version 1, and so will the
        originator when the second event has been applied.
        """
        # Do the work of incrementing the version number.
        next_version = self.__version__ + 1
        # Trigger an event with the result of this work.
        super(VersionedEntity, self).__trigger_event__(
            event_class=event_class, originator_version=next_version, **kwargs
        )

    class Event(
        EventWithOriginatorVersion[TVersionedEntity],
        DomainEntity.Event[TVersionedEntity],
    ):
        """Supertype for events of versioned entities."""

        def __mutate__(
            self, obj: Optional[TVersionedEntity]
        ) -> Optional[TVersionedEntity]:
            obj = super(VersionedEntity.Event, self).__mutate__(obj)
            if obj is not None:
                assert isinstance(obj, VersionedEntity)  # For PyCharm navigation.
                obj.___version__ = self.originator_version
            return obj

        def __check_obj__(self, obj: TVersionedEntity) -> None:
            """
            Extends superclass method by checking the event's
            originator version follows (1 +) this entity's version.
            """
            super(VersionedEntity.Event, self).__check_obj__(obj)
            assert isinstance(obj, VersionedEntity)  # For PyCharm navigation.
            # Assert the version sequence is correct.
            if self.originator_version != obj.__version__ + 1:
                raise OriginatorVersionError(
                    (
                        "Event takes entity to version {}, "
                        "but entity is currently at version {}. "
                        "Event type: '{}', entity type: '{}', entity ID: '{}'"
                        "".format(
                            self.originator_version,
                            obj.__version__,
                            type(self).__name__,
                            type(obj).__name__,
                            obj._id,
                        )
                    )
                )

    class Created(DomainEntity.Created[TVersionedEntity], Event[TVersionedEntity]):
        """Published when a VersionedEntity is created."""

        def __init__(self, originator_version: int = 0, *args: Any, **kwargs: Any):
            super(VersionedEntity.Created, self).__init__(
                originator_version=originator_version, *args, **kwargs
            )

        @property
        def __entity_kwargs__(self) -> Dict[str, Any]:
            # Get super property.
            kwargs = super(VersionedEntity.Created, self).__entity_kwargs__
            kwargs["__version__"] = kwargs.pop("originator_version")
            return kwargs

    class AttributeChanged(
        Event[TVersionedEntity], DomainEntity.AttributeChanged[TVersionedEntity]
    ):
        """Published when a VersionedEntity is changed."""

    class Discarded(Event[TVersionedEntity], DomainEntity.Discarded[TVersionedEntity]):
        """Published when a VersionedEntity is discarded."""


class EntityWithECC(DomainEntity):
    """
    Entity whose events have event ID, correlation ID, and causation ID.
    """

    class Event(DomainEntity.Event):
        def __init__(self, *, processed_event=None, application_name, **kwargs):

            event_id = kwargs.get("event_id") or "{}:{}:{}".format(
                application_name, kwargs["originator_id"], kwargs["originator_version"]
            )
            kwargs["event_id"] = event_id
            if processed_event:
                kwargs["causation_id"] = processed_event.event_id
                kwargs["correlation_id"] = processed_event.correlation_id
            else:
                kwargs["causation_id"] = None
                kwargs["correlation_id"] = event_id

            super().__init__(**kwargs)

        @property
        def event_id(self):
            return self.__dict__["event_id"]

        @property
        def correlation_id(self):
            return self.__dict__["correlation_id"]

        @property
        def causation_id(self):
            return self.__dict__["causation_id"]

    class Created(DomainEntity.Created, Event):
        pass

    class AttributeChanged(Event, DomainEntity.AttributeChanged):
        pass

    class Discarded(Event, DomainEntity.Discarded):
        pass

    def __init__(self, *, event_id, correlation_id, causation_id, **kwargs):
        _ = event_id, correlation_id, causation_id  # accept, but ignore
        super(EntityWithECC, self).__init__(**kwargs)


TTimestampedEntity = TypeVar("TTimestampedEntity", bound="TimestampedEntity")


class TimestampedEntity(DomainEntity):
    def __init__(self, __created_on__: Decimal, **kwargs: Any):
        super(TimestampedEntity, self).__init__(**kwargs)
        self.___created_on__ = __created_on__
        self.___last_modified__ = __created_on__

    @property
    def __created_on__(self) -> Decimal:
        return self.___created_on__

    @property
    def __last_modified__(self) -> Decimal:
        return self.___last_modified__

    class Event(
        DomainEntity.Event[TTimestampedEntity], EventWithTimestamp[TTimestampedEntity]
    ):
        """Supertype for events of timestamped entities."""

        def __mutate__(
            self, obj: Optional[TTimestampedEntity]
        ) -> Optional[TTimestampedEntity]:
            """Updates 'obj' with values from self."""
            obj = super(TimestampedEntity.Event, self).__mutate__(obj)
            if obj is not None:
                assert isinstance(obj, TimestampedEntity)  # For PyCharm navigation.
                obj.___last_modified__ = self.timestamp
            return obj

    class Created(DomainEntity.Created[TTimestampedEntity], Event[TTimestampedEntity]):
        """Published when a TimestampedEntity is created."""

        @property
        def __entity_kwargs__(self) -> Dict[str, Any]:
            # Get super property.
            kwargs = super(TimestampedEntity.Created, self).__entity_kwargs__
            kwargs["__created_on__"] = kwargs.pop("timestamp")
            return kwargs

    class AttributeChanged(
        Event[TTimestampedEntity], DomainEntity.AttributeChanged[TTimestampedEntity]
    ):
        """Published when a TimestampedEntity is changed."""

    class Discarded(
        Event[TTimestampedEntity], DomainEntity.Discarded[TTimestampedEntity]
    ):
        """Published when a TimestampedEntity is discarded."""


# Todo: Move stuff from "test_customise_with_alternative_domain_event_type" in here (
#  to define event classes
#  and update ___last_event_id__ in mutate method).


class TimeuuidedEntity(DomainEntity):
    def __init__(self, event_id: UUID, **kwargs: Any) -> None:
        super(TimeuuidedEntity, self).__init__(**kwargs)
        self.___initial_event_id__ = event_id
        self.___last_event_id__ = event_id

    @property
    def __created_on__(self) -> Decimal:
        return decimaltimestamp_from_uuid(self.___initial_event_id__)

    @property
    def __last_modified__(self) -> Decimal:
        return decimaltimestamp_from_uuid(self.___last_event_id__)


TTimestampedVersionedEntity = TypeVar(
    "TTimestampedVersionedEntity", bound="TimestampedVersionedEntity"
)


class TimestampedVersionedEntity(TimestampedEntity, VersionedEntity):
    class Event(
        TimestampedEntity.Event[TTimestampedVersionedEntity],
        VersionedEntity.Event[TTimestampedVersionedEntity],
    ):
        """Supertype for events of timestamped, versioned entities."""

    class Created(
        TimestampedEntity.Created[TTimestampedVersionedEntity],
        VersionedEntity.Created,
        Event[TTimestampedVersionedEntity],
    ):
        """Published when a TimestampedVersionedEntity is created."""

    class AttributeChanged(
        Event[TTimestampedVersionedEntity],
        TimestampedEntity.AttributeChanged[TTimestampedVersionedEntity],
        VersionedEntity.AttributeChanged[TTimestampedVersionedEntity],
    ):
        """Published when a TimestampedVersionedEntity is created."""

    class Discarded(
        Event[TTimestampedVersionedEntity],
        TimestampedEntity.Discarded[TTimestampedVersionedEntity],
        VersionedEntity.Discarded[TTimestampedVersionedEntity],
    ):
        """Published when a TimestampedVersionedEntity is discarded."""


class TimeuuidedVersionedEntity(TimeuuidedEntity, VersionedEntity):
    pass
