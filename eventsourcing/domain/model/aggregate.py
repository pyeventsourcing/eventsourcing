"""
aggregate
~~~~~~~~~

Base classes for aggregates in a domain driven design.
"""
from collections import deque

from eventsourcing.domain.model.entity import TimestampedVersionedEntity, EntityWithHashchain


class BaseAggregateRoot(TimestampedVersionedEntity):
    """
    Root entity for an aggregate in a domain driven design.
    """

    class Event(TimestampedVersionedEntity.Event):
        """Supertype for aggregate events."""

    class Created(Event, TimestampedVersionedEntity.Created):
        """Published when an AggregateRoot is created."""

    class AttributeChanged(Event, TimestampedVersionedEntity.AttributeChanged):
        """Published when an AggregateRoot is changed."""

    class Discarded(Event, TimestampedVersionedEntity.Discarded):
        """Published when an AggregateRoot is discarded."""

    def __init__(self, **kwargs):
        super(BaseAggregateRoot, self).__init__(**kwargs)
        self.__pending_events__ = deque()

    def __save__(self):
        """
        Publishes pending events for others in application.
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

    def __publish__(self, event):
        """
        Appends event to internal collection of pending events.
        """
        self.__pending_events__.append(event)


class AggregateRootWithHashchainedEvents(EntityWithHashchain, BaseAggregateRoot):

    class Event(EntityWithHashchain.Event, BaseAggregateRoot.Event):
        """Supertype for aggregate events."""

    class Created(Event, EntityWithHashchain.Created, BaseAggregateRoot.Created):
        """Published when an AggregateRoot is created."""

    class AttributeChanged(Event, BaseAggregateRoot.AttributeChanged):
        """Published when an AggregateRoot is changed."""

    class Discarded(Event, EntityWithHashchain.Discarded, BaseAggregateRoot.Discarded):
        """Published when an AggregateRoot is discarded."""


class AggregateRoot(AggregateRootWithHashchainedEvents):

    class Event(AggregateRootWithHashchainedEvents.Event):
        """Supertype for aggregate events."""

    class Created(Event, AggregateRootWithHashchainedEvents.Created):
        """Published when an AggregateRoot is created."""

    class AttributeChanged(Event, AggregateRootWithHashchainedEvents.AttributeChanged):
        """Published when an AggregateRoot is changed."""

    class Discarded(Event, AggregateRootWithHashchainedEvents.Discarded):
        """Published when an AggregateRoot is discarded."""
