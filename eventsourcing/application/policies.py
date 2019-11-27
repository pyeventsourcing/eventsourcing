from typing import Generic, Optional, Tuple, Union, Sequence

from eventsourcing.domain.model.events import (
    EventWithOriginatorVersion,
    subscribe,
    unsubscribe,
)
from eventsourcing.domain.model.snapshot import Snapshot
from eventsourcing.whitehead import TEvent, OneOrManyEvents, IterableOfEvents
from eventsourcing.infrastructure.base import (
    AbstractEventStore,
    AbstractEntityRepository,
)


class PersistencePolicy(object):
    """
    Stores events of given type to given event store, whenever they are published.
    """

    def __init__(
        self,
        event_store: AbstractEventStore,
        persist_event_type: Optional[Union[type, Tuple]] = None,
    ):
        self.event_store = event_store
        self.persist_event_type = persist_event_type
        subscribe(self.store_events, self.is_event)

    def close(self) -> None:
        unsubscribe(self.store_events, self.is_event)

    def is_event(self, events: IterableOfEvents) -> bool:
        if self.persist_event_type is None:
            return False
        else:
            return all(isinstance(e, self.persist_event_type) for e in events)

    def store_events(self, events: IterableOfEvents) -> None:
        self.event_store.store_events(events)


# Todo: Separate PeriodicSnapshottingPolicy from base class? Make usage more
#  configurable.
class SnapshottingPolicy(Generic[TEvent]):
    def __init__(
        self,
        repository: AbstractEntityRepository,
        snapshot_store: AbstractEventStore[Snapshot],
        persist_event_type: Optional[Union[type, Tuple]] = (
            EventWithOriginatorVersion,
        ),
        period: int = 2,
    ):
        self.repository = repository
        self.snapshot_store = snapshot_store
        self.period = period
        self.persist_event_type = persist_event_type
        subscribe(predicate=self.condition, handler=self.take_snapshot)

    def close(self) -> None:
        unsubscribe(predicate=self.condition, handler=self.take_snapshot)

    def condition(self, event: OneOrManyEvents) -> bool:
        # Periodically by default.
        if self.period:
            if isinstance(event, (list, tuple)):
                for e in event:
                    if self.condition(e):
                        return True
            else:
                if self.persist_event_type:
                    if isinstance(event, self.persist_event_type):
                        if isinstance(event, EventWithOriginatorVersion):
                            return (event.originator_version + 1) % self.period == 0
        return False

    def take_snapshot(self, event: OneOrManyEvents) -> None:
        if isinstance(event, (list, tuple)):
            event = event[-1]  # snapshot at the last version
        self.repository.take_snapshot(event.originator_id, lte=event.originator_version)
