from datetime import datetime

from eventsourcing.aggregate import (
    Aggregate,
    get_topic,
    resolve_topic,
)
from eventsourcing.domainevent import DomainEvent


class Snapshot(DomainEvent):
    topic: str
    state: dict

    @classmethod
    def take(cls, aggregate: Aggregate) -> DomainEvent:
        return cls(  # type: ignore
            originator_id=aggregate.id,
            originator_version=aggregate.version,
            timestamp=datetime.now(),
            topic=get_topic(type(aggregate)),
            state=aggregate.__dict__,
        )

    def mutate(self, _=None) -> Aggregate:
        cls = resolve_topic(self.topic)
        aggregate = object.__new__(cls)
        assert isinstance(aggregate, Aggregate)
        aggregate.__dict__.update(self.state)
        return aggregate
