"""
aggregate
~~~~~~~~~

Base classes for aggregates in a domain driven design.
"""
from collections import deque

from eventsourcing.domain.model.entity import TimestampedVersionedEntity
from eventsourcing.exceptions import ConcurrencyError


class AggregateRoot(TimestampedVersionedEntity):
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
        super(AggregateRoot, self).__init__(**kwargs)
        self.__pending_events__ = deque()

    def __save__(self):
        """
        Publishes pending events for others in application.
        """
        batch_of_events = []
        try:
            while True:
                batch_of_events.append(self.__pending_events__.popleft())
        except IndexError:
            pass
        if batch_of_events:
            self.__publish_to_subscribers__(batch_of_events)
            # Don't catch exception and put the events back on the queue.
            # Loosing them here is consistent with the behaviour of DomainEntity
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

    def __publish__(self, event):
        """
        Appends event to internal collection of pending events.
        """
        self.__pending_events__.append(event)

    def __discard__(self):
        super(AggregateRoot, self).__discard__()
        self.__save__()
