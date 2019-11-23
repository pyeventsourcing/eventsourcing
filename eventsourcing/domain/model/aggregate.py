from collections import deque
from typing import Any, Deque, List, Sequence, TypeVar

from eventsourcing.domain.model.entity import (
    EntityWithHashchain,
    TimestampedVersionedEntity,
)

T_ag = TypeVar("T_ag", bound="BaseAggregateRoot")

T_ags = Sequence[T_ag]

T_ag_ev = TypeVar("T_ag_ev", bound="BaseAggregateRoot.Event")

T_ag_evs = Sequence[T_ag_ev]


class BaseAggregateRoot(TimestampedVersionedEntity):
    """
    Root entity for an aggregate in a domain driven design.
    """

    class Event(TimestampedVersionedEntity.Event[T_ag]):
        """Supertype for base aggregate root events."""

    class Created(TimestampedVersionedEntity.Created[T_ag], Event[T_ag]):
        """Triggered when an aggregate root is created."""

    class AttributeChanged(
        Event[T_ag], TimestampedVersionedEntity.AttributeChanged[T_ag]
    ):
        """Triggered when an aggregate root attribute is changed."""

    class Discarded(Event[T_ag], TimestampedVersionedEntity.Discarded[T_ag]):
        """Triggered when an aggregate root is discarded."""

    def __init__(self, **kwargs: Any) -> None:
        super(BaseAggregateRoot, self).__init__(**kwargs)
        self.__pending_events__: Deque[BaseAggregateRoot.Event] = deque()

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

    def __batch_pending_events__(self) -> List["BaseAggregateRoot.Event"]:
        batch_of_events: List["BaseAggregateRoot.Event"] = []
        try:
            while True:
                batch_of_events.append(self.__pending_events__.popleft())
        except IndexError:
            pass
        return batch_of_events


T_ag_hashchain = TypeVar("T_ag_hashchain", bound="AggregateRootWithHashchainedEvents")


class AggregateRootWithHashchainedEvents(EntityWithHashchain, BaseAggregateRoot):
    """Extends aggregate root base class with hash-chained events."""

    class Event(
        EntityWithHashchain.Event[T_ag_hashchain],
        BaseAggregateRoot.Event[T_ag_hashchain],
    ):
        """Supertype for aggregate events."""

    class Created(
        EntityWithHashchain.Created[T_ag_hashchain],
        BaseAggregateRoot.Created[T_ag_hashchain],
        Event[T_ag_hashchain],
    ):
        """Triggered when an aggregate root is created."""

    class AttributeChanged(
        Event[T_ag_hashchain], BaseAggregateRoot.AttributeChanged[T_ag_hashchain]
    ):
        """Triggered when an aggregate root attribute is changed."""

    class Discarded(
        Event[T_ag_hashchain],
        EntityWithHashchain.Discarded[T_ag_hashchain],
        BaseAggregateRoot.Discarded[T_ag_hashchain],
    ):
        """Triggered when an aggregate root is discarded."""


# For backwards compatibility.
class AggregateRoot(AggregateRootWithHashchainedEvents):
    """Original name for aggregate root base class with hash-chained events."""

    class Event(AggregateRootWithHashchainedEvents.Event[T_ag_hashchain]):
        """Supertype for aggregate events."""

    class Created(
        Event[T_ag_hashchain],
        AggregateRootWithHashchainedEvents.Created[T_ag_hashchain],
    ):
        """Triggered when an aggregate root is created."""

    class AttributeChanged(
        Event[T_ag_hashchain],
        AggregateRootWithHashchainedEvents.AttributeChanged[T_ag_hashchain],
    ):
        """Triggered when an aggregate root attribute is changed."""

    class Discarded(
        Event[T_ag_hashchain],
        AggregateRootWithHashchainedEvents.Discarded[T_ag_hashchain],
    ):
        """Triggered when an aggregate root is discarded."""
