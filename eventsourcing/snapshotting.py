from datetime import datetime

from eventsourcing.domain import (
    Aggregate,
)
from eventsourcing.utils import get_topic, resolve_topic
from eventsourcing.domain import DomainEvent


class Snapshot(DomainEvent):
    topic: str
    state: dict

    @classmethod
    def take(cls, aggregate: Aggregate) -> DomainEvent:
        state = dict(aggregate.__dict__)
        state.pop('_pending_events_')
        return cls(  # type: ignore
            originator_id=aggregate.uuid,
            originator_version=aggregate.version,
            timestamp=datetime.now(),
            topic=get_topic(type(aggregate)),
            state=state,
        )

    def mutate(self, _=None) -> Aggregate:
        cls = resolve_topic(self.topic)
        aggregate = object.__new__(cls)
        assert isinstance(aggregate, Aggregate)
        aggregate.__dict__.update(self.state)
        aggregate.__dict__['_pending_events_'] = []
        return aggregate
