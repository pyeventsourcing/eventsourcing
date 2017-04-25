from collections import deque

from eventsourcing.domain.model.entity import TimestampedVersionedEntity
from eventsourcing.domain.model.events import publish


class AggregateRoot(TimestampedVersionedEntity):
    """
    Root entity for an aggregate in a domain driven design.
    """

    def __init__(self, originator_id, originator_version=0, **kwargs):
        super(AggregateRoot, self).__init__(
            originator_id=originator_id, originator_version=originator_version, **kwargs
        )
        self._pending_events = deque()

    def save(self):
        pending_events = []
        try:
            while True:
                pending_events.append(self._pending_events.popleft())
        except IndexError:
            pass
        if pending_events:
            publish(pending_events)

    def _publish(self, event):
        self._pending_events.append(event)
