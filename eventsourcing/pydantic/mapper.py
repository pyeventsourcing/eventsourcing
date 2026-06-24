from __future__ import annotations

from typing import TYPE_CHECKING

from eventsourcing.domain import TAggregateID
from eventsourcing.persistence import Mapper, StoredEvent
from eventsourcing.pydantic.immutablemodel import DomainEvent
from eventsourcing.utils import get_topic, resolve_topic

if TYPE_CHECKING:
    from eventsourcing.domain import DomainEventProtocol


class PydanticMapper(Mapper[TAggregateID]):
    def to_stored_event(
        self, domain_event: DomainEventProtocol[TAggregateID]
    ) -> StoredEvent:
        topic = get_topic(domain_event.__class__)
        assert isinstance(domain_event, DomainEvent)
        stored_state = domain_event.model_dump_json().encode()
        if self.compressor:
            stored_state = self.compressor.compress(stored_state)
        if self.cipher:
            stored_state = self.cipher.encrypt(stored_state)
        return StoredEvent(
            originator_id=domain_event.originator_id,
            originator_version=domain_event.originator_version,
            topic=topic,
            state=stored_state,
        )

    def to_domain_event(
        self, stored_event: StoredEvent
    ) -> DomainEventProtocol[TAggregateID]:
        stored_state = stored_event.state
        if self.cipher:
            stored_state = self.cipher.decrypt(stored_state)
        if self.compressor:
            stored_state = self.compressor.decompress(stored_state)
        cls = resolve_topic(stored_event.topic)
        assert issubclass(cls, DomainEvent)
        return cls.model_validate_json(stored_state.decode())
