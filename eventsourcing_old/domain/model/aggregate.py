from collections import deque
from typing import Any, Deque, Generic, List, Sequence, TypeVar

from eventsourcing.domain.model.entity import (
    DomainEntity,
    EntityWithHashchain,
    TDomainEvent,
    TimestampedVersionedEntity,
)

TAggregate = TypeVar("TAggregate", bound="BaseAggregateRoot")
TAggregateEvent = TypeVar("TAggregateEvent", bound="BaseAggregateRoot.Event")


class BaseAggregateRoot(TimestampedVersionedEntity, Generic[TAggregateEvent]):
    """
    Root entity for an aggregate in a domain driven design.
    """

    class Event(TimestampedVersionedEntity.Event[TAggregate]):
        """Supertype for base aggregate root events."""

    class Created(TimestampedVersionedEntity.Created[TAggregate], Event[TAggregate]):
        """Triggered when an aggregate root is created."""

    class AttributeChanged(
        Event[TAggregate], TimestampedVersionedEntity.AttributeChanged[TAggregate]
    ):
        """Triggered when an aggregate root attribute is changed."""

    class Discarded(
        Event[TAggregate], TimestampedVersionedEntity.Discarded[TAggregate]
    ):
        """Triggered when an aggregate root is discarded."""

    def __init__(self, **kwargs: Any) -> None:
        super(BaseAggregateRoot, self).__init__(**kwargs)
        self.__pending_events__: Deque[DomainEntity.Event] = deque()

    def __publish__(self, event: Sequence[TDomainEvent]) -> None:
        """
        Defers publishing event(s) to subscribers, by adding
        event to internal collection of pending events.
        """
        self.__pending_events__.extend(event)

    def __save__(self) -> None:
        """
        Publishes all pending events to subscribers.
        """
        batch_of_events = self.__batch_pending_events__()
        if batch_of_events:
            self.__publish_to_subscribers__(batch_of_events)
            # Don't catch exception and put the events back on the queue.
            # Losing them here is consistent with the behaviour of DomainEntity
            # when an event cannot be stored: the event is effectively lost, the
            # state of the entity must be reset, and the operation repeated.
            # In case of an aggregate sequence conflict, developers need to
            # know what has happened since the last save, so can retry only the
            # command(s) that have caused conflict. Best to save once per command,
            # so the command can be retried cleanly. The purpose of the save
            # method is to allow many events from one command to be persisted
            # together. The save command can be used to persist all the events
            # from many commands, but in case of a failed save after several
            # commands have been executed, it is important to know which
            # commands to retry.

    def __batch_pending_events__(self) -> List[DomainEntity.Event]:
        batch_of_events: List[DomainEntity.Event] = []
        try:
            while True:
                batch_of_events.append(self.__pending_events__.popleft())
        except IndexError:
            pass
        return batch_of_events


TAggregateRootWithHashchainedEvents = TypeVar(
    "TAggregateRootWithHashchainedEvents", bound="AggregateRootWithHashchainedEvents"
)


class AggregateRootWithHashchainedEvents(EntityWithHashchain, BaseAggregateRoot):
    """Extends aggregate root base class with hash-chained events."""

    class Event(
        EntityWithHashchain.Event[TAggregateRootWithHashchainedEvents],
        BaseAggregateRoot.Event[TAggregateRootWithHashchainedEvents],
    ):
        """Supertype for aggregate events."""

    class Created(
        EntityWithHashchain.Created[TAggregateRootWithHashchainedEvents],
        BaseAggregateRoot.Created[TAggregateRootWithHashchainedEvents],
        Event[TAggregateRootWithHashchainedEvents],
    ):
        """Triggered when an aggregate root is created."""

    class AttributeChanged(
        Event[TAggregateRootWithHashchainedEvents],
        BaseAggregateRoot.AttributeChanged[TAggregateRootWithHashchainedEvents],
    ):
        """Triggered when an aggregate root attribute is changed."""

    class Discarded(
        Event[TAggregateRootWithHashchainedEvents],
        EntityWithHashchain.Discarded[TAggregateRootWithHashchainedEvents],
        BaseAggregateRoot.Discarded[TAggregateRootWithHashchainedEvents],
    ):
        """Triggered when an aggregate root is discarded."""


# For backwards compatibility.
class AggregateRoot(AggregateRootWithHashchainedEvents):
    """Original name for aggregate root base class with hash-chained events."""

    class Event(
        AggregateRootWithHashchainedEvents.Event[TAggregateRootWithHashchainedEvents]
    ):
        """Supertype for aggregate events."""

    class Created(
        Event[TAggregateRootWithHashchainedEvents],
        AggregateRootWithHashchainedEvents.Created[TAggregateRootWithHashchainedEvents],
    ):
        """Triggered when an aggregate root is created."""

    class AttributeChanged(
        Event[TAggregateRootWithHashchainedEvents],
        AggregateRootWithHashchainedEvents.AttributeChanged[
            TAggregateRootWithHashchainedEvents
        ],
    ):
        """Triggered when an aggregate root attribute is changed."""

    class Discarded(
        Event[TAggregateRootWithHashchainedEvents],
        AggregateRootWithHashchainedEvents.Discarded[
            TAggregateRootWithHashchainedEvents
        ],
    ):
        """Triggered when an aggregate root is discarded."""
