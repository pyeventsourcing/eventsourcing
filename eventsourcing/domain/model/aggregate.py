from collections import deque

from eventsourcing.domain.model.entity import (
    TimestampedVersionedEntity,
    EntityWithHashchain,
)


class BaseAggregateRoot(TimestampedVersionedEntity):
    """
    Root entity for an aggregate in a domain driven design.
    """

    class Event(TimestampedVersionedEntity.Event):
        """Supertype for base aggregate root events."""

    class Created(Event, TimestampedVersionedEntity.Created):
        """Triggered when an aggregate root is created."""

    class AttributeChanged(Event, TimestampedVersionedEntity.AttributeChanged):
        """Triggered when an aggregate root attribute is changed."""

    class Discarded(Event, TimestampedVersionedEntity.Discarded):
        """Triggered when an aggregate root is discarded."""

    def __init__(self, **kwargs):
        super(BaseAggregateRoot, self).__init__(**kwargs)
        self.__pending_events__ = deque()

    def __publish__(self, event):
        """
        Overrides super method by adding event
        to internal collection of pending events,
        rather than actually publishing the event.
        """
        self.__pending_events__.append(event)

    def __save__(self):
        """
        Actually publishes all pending events.
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

    def __batch_pending_events__(self):
        batch_of_events = []
        try:
            while True:
                batch_of_events.append(self.__pending_events__.popleft())
        except IndexError:
            pass
        return batch_of_events


class AggregateRootWithHashchainedEvents(EntityWithHashchain, BaseAggregateRoot):
    """Extends aggregate root base class with hash-chained events."""

    class Event(EntityWithHashchain.Event, BaseAggregateRoot.Event):
        """Supertype for aggregate events."""

    class Created(Event, EntityWithHashchain.Created, BaseAggregateRoot.Created):
        """Triggered when an aggregate root is created."""

    class AttributeChanged(Event, BaseAggregateRoot.AttributeChanged):
        """Triggered when an aggregate root attribute is changed."""

    class Discarded(Event, EntityWithHashchain.Discarded, BaseAggregateRoot.Discarded):
        """Triggered when an aggregate root is discarded."""


class AggregateRoot(AggregateRootWithHashchainedEvents):
    """Original name for aggregate root base class with hash-chained events."""

    class Event(AggregateRootWithHashchainedEvents.Event):
        """Supertype for aggregate events."""

    class Created(Event, AggregateRootWithHashchainedEvents.Created):
        """Triggered when an aggregate root is created."""

    class AttributeChanged(Event, AggregateRootWithHashchainedEvents.AttributeChanged):
        """Triggered when an aggregate root attribute is changed."""

    class Discarded(Event, AggregateRootWithHashchainedEvents.Discarded):
        """Triggered when an aggregate root is discarded."""
