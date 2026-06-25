from __future__ import annotations

import inspect
from typing import TYPE_CHECKING

import msgspec

from eventsourcing.domain import TAggregateID
from eventsourcing.persistence import Mapper, StoredEvent
from eventsourcing.utils import get_topic, resolve_topic

if TYPE_CHECKING:
    from eventsourcing.domain import DomainEventProtocol


class MsgspecMapper(Mapper[TAggregateID]):
    def to_stored_event(
        self, domain_event: DomainEventProtocol[TAggregateID]
    ) -> StoredEvent:
        topic = get_topic(domain_event.__class__)
        stored_state = msgspec.json.encode(domain_event)
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
        try:
            return msgspec.json.decode(stored_state, type=cls)
        except Exception as e:
            msg = (
                f"Failed to decode msgspec struct: {cls} with {stored_event}: {e}."
                f"\nClass signature: {inspect.signature(cls)}"
                f"\noriginator_id_type: {cls.originator_id_type}"
                f"\nMRO: \n" + "\n  - ".join(str(c) for c in cls.__mro__)
            )
            raise type(e)(msg) from e
