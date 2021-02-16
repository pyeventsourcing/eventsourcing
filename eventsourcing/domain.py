import os
from dataclasses import dataclass
from datetime import datetime, tzinfo
from typing import Any, Generic, List, Optional, Type, TypeVar, cast
from uuid import UUID

from eventsourcing.utils import get_topic, resolve_topic

TZINFO: tzinfo = resolve_topic(os.getenv("TZINFO_TOPIC", "datetime:timezone.utc"))


@dataclass(frozen=True)
class DomainEvent:
    """
    Base class for domain events, such as aggregate :class:`Aggregate.Event`
    and aggregate :class:`Snapshot`.

    Constructor arguments:

    :param UUID originator_id: ID of originating aggregate.
    :param int originator_version: version of originating aggregate.
    :param datetime timestamp: date-time of the event
    """

    originator_id: UUID
    originator_version: int
    timestamp: datetime


TDomainEvent = TypeVar("TDomainEvent", bound=DomainEvent)
TAggregate = TypeVar("TAggregate", bound="BaseAggregate")
TAggregateEvent = TypeVar("TAggregateEvent", bound="BaseAggregate.Event")
TAggregateCreated = TypeVar("TAggregateCreated", bound="BaseAggregate.Created")


class MetaAggregate(type):
    pass


class BaseAggregate(metaclass=MetaAggregate):
    """
    Base class for aggregate roots.
    """

    def __init__(self, id: UUID, version: int, timestamp: datetime):
        """
        Initialises an aggregate object with an :data:`id`, a :data:`version`
        number, and a :data:`timestamp`. The internal :data:`_pending_events` list
        is also initialised.
        """
        self._id = id
        self._version = version
        self._created_on = timestamp
        self._modified_on = timestamp
        self._pending_events: List[Aggregate.Event] = []

    @property
    def id(self) -> UUID:
        """
        The ID of the aggregate.
        """
        return self._id

    @property
    def version(self) -> int:
        """
        The current version of the aggregate.
        """
        return self._version

    @property
    def created_on(self) -> datetime:
        """
        The date and time when the aggregate was created.
        """
        return self._created_on

    @property
    def modified_on(self) -> datetime:
        """
        The date and time when the aggregate was last modified.
        """
        return self._modified_on

    class Event(DomainEvent, Generic[TAggregate]):
        """
        Base class for aggregate events. Subclasses will model
        decisions made by the domain model aggregates.

        Constructor arguments:

        :param UUID originator_id: ID of originating aggregate.
        :param int originator_version: version of originating aggregate.
        :param datetime timestamp: date-time of the event
        """

        def mutate(self, obj: Optional[TAggregate]) -> Optional[TAggregate]:
            """
            Changes the state of the aggregate
            according to domain event attributes.
            """
            # Check event is next in its sequence.
            # Use counting to follow the sequence.
            # assert isinstance(obj, Aggregate), (type(obj), self)
            assert obj is not None
            next_version = obj._version + 1
            if self.originator_version != next_version:
                raise VersionError(self.originator_version, next_version)
            # Update the aggregate version.
            obj._version = next_version
            # Update the modified time.
            obj._modified_on = self.timestamp
            self.apply(obj)
            return obj

        def apply(self, aggregate: TAggregate) -> None:
            """
            Applies the domain event to the aggregate.
            """

    @classmethod
    def _create(
        cls: Type[TAggregate],
        event_class: Type[TAggregateCreated],
        *,
        id: UUID,
        **kwargs: Any,
    ) -> TAggregate:
        """
        Factory method to construct a new
        aggregate object instance.
        """
        # Construct the domain event class,
        # with an ID and version, and the
        # a topic for the aggregate class.
        try:
            event: TAggregateCreated = event_class(  # type: ignore
                originator_topic=get_topic(cls),
                originator_id=id,
                originator_version=1,
                timestamp=datetime.now(tz=TZINFO),
                **kwargs,
            )
        except TypeError as e:
            msg = (
                f"Unable to construct 'aggregate created' "
                f"event with class {event_class.__qualname__} "
                f"and keyword args {kwargs}: {e}"
            )
            raise TypeError(msg)
        # Construct the aggregate object.
        aggregate: TAggregate = event.mutate(None)
        # Append the domain event to pending list.
        aggregate._pending_events.append(event)
        # Return the aggregate.
        return aggregate

    @dataclass(frozen=True)
    class Created(Event["Aggregate"]):
        """
        Domain event for when aggregate is created.

        Constructor arguments:

        :param UUID originator_id: ID of originating aggregate.
        :param int originator_version: version of originating aggregate.
        :param datetime timestamp: date-time of the event
        :param str originator_topic: topic for the aggregate class
        """

        originator_topic: str

        def mutate(self, obj: Optional[TAggregate]) -> TAggregate:
            """
            Constructs aggregate instance defined
            by domain event object attributes.
            """
            assert obj is None
            # Copy the event attributes.
            kwargs = self.__dict__.copy()
            # Resolve originator topic.
            aggregate_class: Type[TAggregate] = resolve_topic(
                kwargs.pop("originator_topic")
            )
            # Separate the base class keywords arguments.
            # Construct and return aggregate object.
            kwargs["id"] = kwargs.pop("originator_id")
            kwargs["version"] = kwargs.pop("originator_version")

            aggregate = cast(TAggregate, object.__new__(aggregate_class))
            aggregate.__init__(**kwargs)
            return aggregate

    def _trigger_event(
        self,
        event_class: Type[TAggregateEvent],
        **kwargs: Any,
    ) -> None:
        """
        Triggers domain event of given type, by creating
        an event object and using it to mutate the aggregate.
        """
        # Construct the domain event as the
        # next in the aggregate's sequence.
        # Use counting to generate the sequence.
        next_version = self.version + 1
        try:
            event = event_class(  # type: ignore
                originator_id=self.id,
                originator_version=next_version,
                timestamp=datetime.now(tz=TZINFO),
                **kwargs,
            )
        except TypeError as e:
            raise TypeError(f"Can't construct event {event_class}: {e}")

        # Mutate aggregate with domain event.
        event.mutate(self)
        # Append the domain event to pending list.
        self._pending_events.append(event)

    def collect_events(self) -> List[Event]:
        """
        Collects and returns a list of pending aggregate
        :class:`Aggregate.Event` objects.
        """
        collected = []
        while self._pending_events:
            collected.append(self._pending_events.pop(0))
        return collected


class Aggregate(BaseAggregate):
    pass


class VersionError(Exception):
    """
    Raised when a domain event can't be applied to
    an aggregate due to version mismatch indicating
    the domain event is not the next in the aggregate's
    sequence of events.
    """


@dataclass(frozen=True)
class Snapshot(DomainEvent):
    """
    Snapshots represent the state of an aggregate at a particular
    version.

    Constructor arguments:

    :param UUID originator_id: ID of originating aggregate.
    :param int originator_version: version of originating aggregate.
    :param datetime timestamp: date-time of the event
    :param str topic: string that includes a class and its module
    :param dict state: version of originating aggregate.
    """

    topic: str
    state: dict

    @classmethod
    def take(cls, aggregate: TAggregate) -> "Snapshot":
        """
        Creates a snapshot of the given :class:`Aggregate` object.
        """
        aggregate_state = dict(aggregate.__dict__)
        aggregate_state.pop("_pending_events")
        class_version = getattr(type(aggregate), "class_version", 1)
        if class_version > 1:
            aggregate_state["class_version"] = class_version
        originator_id = aggregate_state.pop("_id")
        originator_version = aggregate_state.pop("_version")
        return cls(
            originator_id=originator_id,
            originator_version=originator_version,
            timestamp=datetime.now(tz=TZINFO),
            topic=get_topic(type(aggregate)),
            state=aggregate_state,
        )

    def mutate(self, _: None = None) -> TAggregate:
        """
        Reconstructs the snapshotted :class:`Aggregate` object.
        """
        cls = resolve_topic(self.topic)
        assert issubclass(cls, Aggregate)
        aggregate_state = dict(self.state)
        from_version = aggregate_state.pop("class_version", 1)
        class_version = getattr(cls, "class_version", 1)
        while from_version < class_version:
            upcast_name = f"upcast_v{from_version}_v{from_version + 1}"
            upcast = getattr(cls, upcast_name)
            upcast(aggregate_state)
            from_version += 1

        aggregate_state["_id"] = self.originator_id
        aggregate_state["_version"] = self.originator_version
        aggregate_state["_pending_events"] = []
        aggregate = object.__new__(cls)
        aggregate.__dict__.update(aggregate_state)
        return aggregate
