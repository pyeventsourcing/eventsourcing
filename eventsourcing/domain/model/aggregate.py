from collections import deque

from eventsourcing.domain.model.entity import TimestampedVersionedEntity
from eventsourcing.domain.model.events import publish


class AggregateRoot(TimestampedVersionedEntity):
    """
    Root entity for an aggregate in a domain driven design.
    """
    class Event(TimestampedVersionedEntity.Event):
        """Layer supertype."""

    class Created(Event, TimestampedVersionedEntity.Created):
        """Published when an AggregateRoot is created."""

    class AttributeChanged(Event, TimestampedVersionedEntity.AttributeChanged):
        """Published when an AggregateRoot is changed."""

    class Discarded(Event, TimestampedVersionedEntity.Discarded):
        """Published when an AggregateRoot is discarded."""

    def __init__(self, **kwargs):
        super(AggregateRoot, self).__init__(**kwargs)
        self._pending_events = deque()

    def _publish(self, event):
        """
        Appends event to internal collection of pending events.
        """
        self._pending_events.append(event)

    def save(self):
        """
        Publishes pending events for others in application.
        """
        batch_of_events = []
        try:
            while True:
                batch_of_events.append(self._pending_events.popleft())
        except IndexError:
            pass
        if batch_of_events:
            publish(batch_of_events)
