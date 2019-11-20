from collections import deque
from typing import Deque, List, Sequence, TypeVar, Any

from eventsourcing.domain.model.entity import (
    EntityWithHashchain,
    TimestampedVersionedEntity,
)
from eventsourcing.types import T_en

T_ag = TypeVar("T_ag", bound='BaseAggregateRoot')

T_ags = Sequence[T_ag]

T_ag_ev = TypeVar("T_ag_ev", bound="BaseAggregateRoot.Event")

T_ag_evs = Sequence[T_ag_ev]


class BaseAggregateRoot(TimestampedVersionedEntity[T_ag_ev]):
    """
    Root entity for an aggregate in a domain driven design.
    """

    class Event(TimestampedVersionedEntity.Event[T_en]):
        """Supertype for base aggregate root events."""

    class Created(Event[T_en], TimestampedVersionedEntity.Created[T_en]):
        """Triggered when an aggregate root is created."""

    class AttributeChanged(Event[T_en],
                           TimestampedVersionedEntity.AttributeChanged[T_en]):
        """Triggered when an aggregate root attribute is changed."""

    class Discarded(Event[T_en], TimestampedVersionedEntity.Discarded[T_en]):
        """Triggered when an aggregate root is discarded."""

    def __init__(self, **kwargs: Any) -> None:
        super(BaseAggregateRoot, self).__init__(**kwargs)
        self.__pending_events__: Deque[T_ag_ev] = deque()

    def __publish__(self, ev_or_evs: T_ag_evs) -> None:
        """
        Defers publishing event(s) to subscribers, by adding
        event to internal collection of pending events.
        """
        if isinstance(ev_or_evs, Sequence):
            self.__pending_events__.extend(ev_or_evs)
        else:
            self.__pending_events__.append(ev_or_evs)

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

    def __batch_pending_events__(self) -> List[T_ag_ev]:
        batch_of_events: List[T_ag_ev] = []
        try:
            while True:
                batch_of_events.append(self.__pending_events__.popleft())
        except IndexError:
            pass
        return batch_of_events


class AggregateRootWithHashchainedEvents(EntityWithHashchain, BaseAggregateRoot):
    """Extends aggregate root base class with hash-chained events."""

    class Event(EntityWithHashchain.Event[T_en], BaseAggregateRoot.Event[T_en]):
        """Supertype for aggregate events."""

    class Created(
        Event[T_en], EntityWithHashchain.Created[T_en], BaseAggregateRoot.Created[T_en]
    ):
        """Triggered when an aggregate root is created."""

    class AttributeChanged(Event[T_en], BaseAggregateRoot.AttributeChanged[T_en]):
        """Triggered when an aggregate root attribute is changed."""

    class Discarded(
        Event[T_en], EntityWithHashchain.Discarded[T_en],
        BaseAggregateRoot.Discarded[T_en]
    ):
        """Triggered when an aggregate root is discarded."""


class AggregateRoot(AggregateRootWithHashchainedEvents):
    """Original name for aggregate root base class with hash-chained events."""

    class Event(AggregateRootWithHashchainedEvents.Event[T_en]):
        """Supertype for aggregate events."""

    class Created(Event[T_en], AggregateRootWithHashchainedEvents.Created[T_en]):
        """Triggered when an aggregate root is created."""

    class AttributeChanged(
        Event[T_en], AggregateRootWithHashchainedEvents.AttributeChanged[T_en]
    ):
        """Triggered when an aggregate root attribute is changed."""

    class Discarded(Event[T_en], AggregateRootWithHashchainedEvents.Discarded[T_en]):
        """Triggered when an aggregate root is discarded."""
