from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Type, TypeVar
from uuid import UUID

from eventsourcing.utils import get_topic, resolve_topic


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
            next_version = obj.version + 1
            if self.originator_version != next_version:
                raise VersionError(self.originator_version, next_version)
            # Update the aggregate version.
            obj.version = next_version
            # Update the modified time.
            obj.modified_on = self.timestamp
            self.apply(obj)
            return obj

        def apply(self, obj) -> None:
            pass

    def __init__(self, uuid: UUID, version: int, timestamp: datetime):
        """
        Aggregate is constructed with a 'uuid',
        a 'version', and a 'timestamp'. The internal
        '_pending_events_' list is also initialised.
        """
        self.uuid = uuid
        self.version = version
        self.created_on = timestamp
        self.modified_on = timestamp
        self._pending_events_: List[Aggregate.Event] = []

    @classmethod
    def _create_(
        cls,
        event_class: Type["Aggregate.Created"],
        uuid: UUID,
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
            originator_id=uuid,
            originator_version=1,
            originator_topic=get_topic(cls),
            timestamp=datetime.now(),
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
            # Separate the id and version.
            uuid = kwargs.pop("originator_id")
            version = kwargs.pop("originator_version")
            # Get the aggregate root class from topic.
            aggregate_class = resolve_topic(kwargs.pop("originator_topic"))
            # Construct and return aggregate object.
            return aggregate_class(uuid=uuid, version=version, **kwargs)

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
        next_version = self.version + 1
        event = event_class(
            originator_id=self.uuid,
            originator_version=next_version,
            timestamp=datetime.now(),
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
        return cls(  # type: ignore
            originator_id=aggregate.uuid,
            originator_version=aggregate.version,
            timestamp=datetime.now(),
            topic=get_topic(type(aggregate)),
            state=state,
        )

    def mutate(self, _=None) -> Aggregate:
        cls = resolve_topic(self.topic)
        aggregate = object.__new__(cls)
        assert isinstance(aggregate, Aggregate)
        aggregate.__dict__.update(self.state)
        aggregate.__dict__["_pending_events_"] = []
        return aggregate
