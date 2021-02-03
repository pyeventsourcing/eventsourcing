import os
from dataclasses import dataclass
from datetime import datetime, tzinfo
from typing import List, Optional, Type, TypeVar
from uuid import UUID

from eventsourcing.utils import get_topic, resolve_topic

TZINFO: tzinfo = resolve_topic(
    os.getenv('TZINFO_TOPIC', 'datetime:timezone.utc')
)


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


class Aggregate:
    """
    Base class for aggregate roots.
    """

    def __init__(self, id: UUID, _version_: int, _created_on_: datetime):
        """
        Initialises an aggregate object with a :data:`id`, a :data:`_version_`,
        and a :data:`_created_on_`. The internal :data:`_pending_events_` list
        is also initialised.
        """
        self.id = id
        self._version_ = _version_
        self._created_on_ = _created_on_
        self._modified_on_ = _created_on_
        self._pending_events_: List[Aggregate.Event] = []

    @dataclass(frozen=True)
    class Event(DomainEvent):
        """
        Base class for aggregate events. Subclasses will model
        decisions made by the domain model aggregates.

        Constructor arguments:

        :param UUID originator_id: ID of originating aggregate.
        :param int originator_version: version of originating aggregate.
        :param datetime timestamp: date-time of the event
        """

        def mutate(self, obj: Optional["Aggregate"]) -> Optional["Aggregate"]:
            """
            Changes the state of the aggregate
            according to domain event attributes.
            """
            # Check event is next in its sequence.
            # Use counting to follow the sequence.
            assert isinstance(obj, Aggregate), (type(obj), self)
            next_version = obj._version_ + 1
            if self.originator_version != next_version:
                raise VersionError(self.originator_version, next_version)
            # Update the aggregate version.
            obj._version_ = next_version
            # Update the modified time.
            obj._modified_on_ = self.timestamp
            self.apply(obj)
            return obj

        def apply(self, aggregate: "Aggregate") -> None:
            """
            Applies the domain event to the aggregate.
            """
            pass

    @classmethod
    def _create_(
        cls,
        event_class: Type["Aggregate.Created"],
        id: UUID,
        **kwargs,
    ):
        """
        Factory method to construct a new
        aggregate object instance.
        """
        # Construct the domain event class,
        # with an ID and version, and the
        # a topic for the aggregate class.
        try:
            event = event_class(
                originator_topic=get_topic(cls),
                originator_id=id,
                originator_version=1,
                timestamp=datetime.now(tz=TZINFO),
                **kwargs,
            )
        except TypeError as e:
            msg = (
                f"Unable to construct event with class {event_class.__qualname__} "
                f"and keyword args {kwargs}: {e}"
            )
            raise TypeError(msg)
        # Construct the aggregate object.
        aggregate = event.mutate(None)
        # Append the domain event to pending list.
        aggregate._pending_events_.append(event)
        # Return the aggregate.
        return aggregate

    @dataclass(frozen=True)
    class Created(Event):
        """
        Domain event for when aggregate is created.

        Constructor arguments:

        :param UUID originator_id: ID of originating aggregate.
        :param int originator_version: version of originating aggregate.
        :param datetime timestamp: date-time of the event
        :param str topic: string that includes a class and its module
        :param str originator_topic: topic of aggregate class
        """

        originator_topic: str

        def mutate(self, obj: Optional["Aggregate"]) -> "Aggregate":
            """
            Constructs aggregate instance defined
            by domain event object attributes.
            """
            # Copy the event attributes.
            kwargs = self.__dict__.copy()
            # Resolve originator topic.
            aggregate_class = resolve_topic(kwargs.pop("originator_topic"))
            # Separate the base class keywords arguments.
            id = kwargs.pop("originator_id")
            _version_ = kwargs.pop("originator_version")
            _created_on_ = kwargs.pop("timestamp")
            # Construct and return aggregate object.
            return aggregate_class(
                id=id,
                _version_=_version_,
                _created_on_=_created_on_,
                **kwargs
            )

    def _trigger_(
        self,
        event_class: Type["Aggregate.Event"],
        **kwargs,
    ) -> None:
        """
        Triggers domain event of given type,
        extending the sequence of domain
        events for this aggregate object.
        """
        # Construct the domain event as the
        # next in the aggregate's sequence.
        # Use counting to generate the sequence.
        next_version = self._version_ + 1
        event = event_class(
            originator_id=self.id,
            originator_version=next_version,
            timestamp=datetime.now(tz=TZINFO),
            **kwargs,
        )
        # Mutate aggregate with domain event.
        event.mutate(self)
        # Append the domain event to pending list.
        self._pending_events_.append(event)

    def _collect_(self) -> List[Event]:
        """
        Collects and returns a list of pending aggregate
        :class:`Aggregate.Event` objects.
        """
        collected = []
        while self._pending_events_:
            collected.append(self._pending_events_.pop(0))
        return collected


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
    def take(cls, aggregate: Aggregate) -> DomainEvent:
        """
        Creates a snapshot of the given :class:`Aggregate` object.
        """
        aggregate_state = dict(aggregate.__dict__)
        aggregate_state.pop("_pending_events_")
        class_version = getattr(type(aggregate), '_class_version_', 1)
        if class_version > 1:
            aggregate_state['_class_version_'] = class_version
        originator_id = aggregate_state.pop("id")
        originator_version = aggregate_state.pop("_version_")
        return cls(
            originator_id=originator_id,
            originator_version=originator_version,
            timestamp=datetime.now(tz=TZINFO),
            topic=get_topic(type(aggregate)),
            state=aggregate_state,
        )

    def mutate(self, _=None) -> Aggregate:
        """
        Reconstructs the snapshotted :class:`Aggregate` object.
        """
        cls = resolve_topic(self.topic)
        assert issubclass(cls, Aggregate)
        aggregate_state = dict(self.state)
        from_version = aggregate_state.pop('_class_version_', 1)
        class_version = getattr(cls, '_class_version_', 1)
        while from_version < class_version:
            upcast_name = f'_upcast_v{from_version}_v{from_version + 1}_'
            upcast = getattr(cls, upcast_name)
            upcast(aggregate_state)
            from_version += 1

        aggregate_state["id"] = self.originator_id
        aggregate_state["_version_"] = self.originator_version
        aggregate_state["_pending_events_"] = []
        aggregate = object.__new__(cls)
        aggregate.__dict__.update(aggregate_state)
        return aggregate
