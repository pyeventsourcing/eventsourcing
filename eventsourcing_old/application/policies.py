from typing import Generic, Optional, Tuple, Union

from eventsourcing.domain.model.entity import VersionedEntity
from eventsourcing.domain.model.events import (
    AbstractSnapshot,
    EventWithOriginatorVersion,
    subscribe,
    unsubscribe,
)
from eventsourcing.domain.model.repository import AbstractEntityRepository
from eventsourcing.infrastructure.base import AbstractEventStore, AbstractRecordManager
from eventsourcing.whitehead import IterableOfEvents, TEvent


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
        elif type(events) not in [list, tuple]:
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
        snapshot_store: AbstractEventStore[AbstractSnapshot, AbstractRecordManager],
        persist_event_type: Optional[Union[type, Tuple]] = (
            EventWithOriginatorVersion,
        ),
        period: int = 0,
    ):
        self.repository = repository
        self.snapshot_store = snapshot_store
        self.period = period
        self.persist_event_type = persist_event_type
        subscribe(predicate=self.condition, handler=self.take_snapshot)

    def close(self) -> None:
        unsubscribe(predicate=self.condition, handler=self.take_snapshot)

    def condition(self, event: IterableOfEvents) -> bool:
        # Periodically by default.
        if self.persist_event_type and isinstance(self.period, int) and self.period > 0:
            if isinstance(event, (list, tuple)):
                for e in event:
                    if self.condition(e):
                        return True
            else:
                if isinstance(event, self.persist_event_type):
                    if isinstance(event, VersionedEntity.Event):
                        return (event.originator_version + 1) % self.period == 0
        return False

    def take_snapshot(self, events: IterableOfEvents) -> None:
        event = list(events)[-1]  # snapshot at the last version
        assert isinstance(event, VersionedEntity.Event), type(event)
        self.repository.take_snapshot(event.originator_id, lte=event.originator_version)
