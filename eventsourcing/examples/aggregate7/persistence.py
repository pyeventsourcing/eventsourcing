from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, cast

import orjson
from pydantic import BaseModel

from eventsourcing.persistence import (
    Mapper,
    ProgrammingError,
    StoredEvent,
    Transcoder,
    Transcoding,
)
from eventsourcing.utils import get_topic, resolve_topic

if TYPE_CHECKING:  # pragma: nocover
    from eventsourcing.domain import DomainEventProtocol


class PydanticMapper(Mapper):
    def to_stored_event(self, domain_event: DomainEventProtocol) -> StoredEvent:
        topic = get_topic(domain_event.__class__)
        event_state = cast(BaseModel, domain_event).model_dump()
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

    def to_domain_event(self, stored: StoredEvent) -> DomainEventProtocol:
        stored_state = stored.state
        if self.cipher:
            stored_state = self.cipher.decrypt(stored_state)
        if self.compressor:
            stored_state = self.compressor.decompress(stored_state)
        event_state: Dict[str, Any] = self.transcoder.decode(stored_state)
        cls = resolve_topic(stored.topic)
        return cls(**event_state)


class OrjsonTranscoder(Transcoder):
    def encode(self, obj: Any) -> bytes:
        return orjson.dumps(obj)

    def decode(self, data: bytes) -> Any:
        return orjson.loads(data)

    def register(self, _: Transcoding) -> None:  # pragma: no cover
        msg = "Please use Pydantic BaseModel"
        raise ProgrammingError(msg)
