from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, cast

import orjson
from pydantic import BaseModel

from eventsourcing.application import Application
from eventsourcing.persistence import Mapper, StoredEvent, Transcoder
from eventsourcing.utils import get_topic, resolve_topic

if TYPE_CHECKING:
    from eventsourcing.domain import DomainEventProtocol


class PydanticMapper(Mapper):
    def to_stored_event(self, domain_event: DomainEventProtocol) -> StoredEvent:
        topic = get_topic(domain_event.__class__)
        event_state = cast(BaseModel, domain_event).model_dump(mode="json")
        stored_state = self.transcoder.encode(event_state)
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

    def to_domain_event(self, stored_event: StoredEvent) -> DomainEventProtocol:
        stored_state = stored_event.state
        if self.cipher:
            stored_state = self.cipher.decrypt(stored_state)
        if self.compressor:
            stored_state = self.compressor.decompress(stored_state)
        event_state: dict[str, Any] = self.transcoder.decode(stored_state)
        cls = resolve_topic(stored_event.topic)
        return cls(**event_state)


class OrjsonTranscoder(Transcoder):
    def encode(self, obj: Any) -> bytes:
        return orjson.dumps(obj)

    def decode(self, data: bytes) -> Any:
        return orjson.loads(data)


class PydanticApplication(Application):
    env: ClassVar[dict[str, str]] = {
        "TRANSCODER_TOPIC": get_topic(OrjsonTranscoder),
        "MAPPER_TOPIC": get_topic(PydanticMapper),
    }
