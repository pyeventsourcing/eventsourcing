from collections import deque
from typing import List, Union, Sequence

from eventsourcing.domain.model.entity import (
    EntityWithHashchain,
    TimestampedVersionedEntity,
)
from eventsourcing.types import AbstractDomainEvent, T


class BaseAggregateRoot(TimestampedVersionedEntity[T]):
    """
    Root entity for an aggregate in a domain driven design.
    """

    class Event(TimestampedVersionedEntity.Event[T]):
        """Supertype for base aggregate root events."""

    class Created(Event[T], TimestampedVersionedEntity.Created[T]):
        """Triggered when an aggregate root is created."""

    class AttributeChanged(Event[T], TimestampedVersionedEntity.AttributeChanged[T]):
        """Triggered when an aggregate root attribute is changed."""

    class Discarded(Event[T], TimestampedVersionedEntity.Discarded[T]):
        """Triggered when an aggregate root is discarded."""

    def __init__(self, **kwargs):
        super(BaseAggregateRoot, self).__init__(**kwargs)
        self.__pending_events__ = deque()

    def __publish__(self, event: Union[AbstractDomainEvent, List[AbstractDomainEvent]]):
        """
        Defers publishing event to subscribers, by adding
        event to internal collection of pending events.
        """
        self.__pending_events__.append(event)

    def __save__(self) -> None:
        """
        Publishes all pending events to subscribers.
        """
        batch_of_events: Sequence[
            BaseAggregateRoot.Event
        ] = self.__batch_pending_events__()
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

    def __batch_pending_events__(self) -> List[Event]:
        batch_of_events: List[BaseAggregateRoot.Event] = []
        try:
            while True:
                batch_of_events.append(self.__pending_events__.popleft())
        except IndexError:
            pass
        return batch_of_events


class AggregateRootWithHashchainedEvents(EntityWithHashchain[T], BaseAggregateRoot[T]):
    """Extends aggregate root base class with hash-chained events."""

    class Event(EntityWithHashchain.Event[T], BaseAggregateRoot.Event[T]):
        """Supertype for aggregate events."""

    class Created(
        Event[T], EntityWithHashchain.Created[T], BaseAggregateRoot.Created[T]
    ):
        """Triggered when an aggregate root is created."""

    class AttributeChanged(Event[T], BaseAggregateRoot.AttributeChanged[T]):
        """Triggered when an aggregate root attribute is changed."""

    class Discarded(
        Event[T], EntityWithHashchain.Discarded[T], BaseAggregateRoot.Discarded[T]
    ):
        """Triggered when an aggregate root is discarded."""


class AggregateRoot(AggregateRootWithHashchainedEvents[T]):
    """Original name for aggregate root base class with hash-chained events."""

    class Event(AggregateRootWithHashchainedEvents.Event[T]):
        """Supertype for aggregate events."""

    class Created(Event[T], AggregateRootWithHashchainedEvents.Created[T]):
        """Triggered when an aggregate root is created."""

    class AttributeChanged(
        Event[T], AggregateRootWithHashchainedEvents.AttributeChanged[T]
    ):
        """Triggered when an aggregate root attribute is changed."""

    class Discarded(Event[T], AggregateRootWithHashchainedEvents.Discarded[T]):
        """Triggered when an aggregate root is discarded."""
