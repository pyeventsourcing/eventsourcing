import os
from dataclasses import dataclass
from datetime import datetime, tzinfo
from typing import List, Optional, Type, TypeVar
from uuid import UUID

from eventsourcing.utils import get_topic, resolve_topic

TZINFO: tzinfo = resolve_topic(
    os.getenv('TZINFO_TOPIC', 'datetime:timezone.utc')
)


class FrozenDataClass(type):
    def __new__(cls, *args):
        new_cls = super().__new__(cls, *args)
        return dataclass(frozen=True)(new_cls)


class ImmutableObject(metaclass=FrozenDataClass):
    pass


class DomainEvent(ImmutableObject):
    originator_id: UUID
    originator_version: int
    timestamp: datetime


TDomainEvent = TypeVar("TDomainEvent", bound=DomainEvent)


class Aggregate:
    """
    Base class for aggregate roots.
    """

    class Event(DomainEvent):
        """
        Base domain event class for aggregates.
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

        def apply(self, obj) -> None:
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
        event = event_class(
            originator_topic=get_topic(cls),
            originator_id=id,
            originator_version=1,
            timestamp=datetime.now(tz=TZINFO),
            **kwargs,
        )
        # Construct the aggregate object.
        aggregate = event.mutate(None)
        # Append the domain event to pending list.
        aggregate._pending_events_.append(event)
        # Return the aggregate.
        return aggregate

    class Created(Event):
        """
        Domain event for when aggregate is created.
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

    def __init__(self, id: UUID, _version_: int, _created_on_: datetime):
        """
        Aggregate is constructed with a 'uuid',
        a 'version', and a 'timestamp'. The internal
        '_pending_events_' list is also initialised.
        """
        self.id = id
        self._version_ = _version_
        self._created_on_ = _created_on_
        self._modified_on_ = _created_on_
        self._pending_events_: List[Aggregate.Event] = []

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
        Collects pending events.
        """
        collected = []
        while self._pending_events_:
            collected.append(self._pending_events_.pop(0))
        return collected


class VersionError(Exception):
    pass


class Snapshot(DomainEvent):
    topic: str
    state: dict

    @classmethod
    def take(cls, aggregate: Aggregate) -> DomainEvent:
        state = dict(aggregate.__dict__)
        state.pop("_pending_events_")
        originator_id = state.pop("id")
        originator_version = state.pop("_version_")
        return cls(
            originator_id=originator_id,
            originator_version=originator_version,
            timestamp=datetime.now(tz=TZINFO),
            topic=get_topic(type(aggregate)),
            state=state,
        )

    def mutate(self, _=None) -> Aggregate:
        cls = resolve_topic(self.topic)
        aggregate = object.__new__(cls)
        assert isinstance(aggregate, Aggregate)
        aggregate.__dict__.update(self.state)
        aggregate.__dict__["id"] = self.originator_id
        aggregate.__dict__["_version_"] = self.originator_version
        aggregate.__dict__["_pending_events_"] = []
        return aggregate
