from typing import Any, Dict, cast

import orjson
from pydantic import BaseModel

from eventsourcing.domain import HasOriginatorIDVersion, THasOriginatorIDVersion, \
    OriginatorIDVersionProtocol
from eventsourcing.persistence import (
    Mapper,
    ProgrammingError,
    StoredEvent,
    Transcoder,
    Transcoding,
)
from eventsourcing.utils import get_topic, resolve_topic


class PydanticMapper(Mapper):
    def to_stored_event(self, domain_event: OriginatorIDVersionProtocol) -> StoredEvent:
        topic = get_topic(domain_event.__class__)
        event_state = cast(BaseModel, domain_event).dict()
        stored_state = self.transcoder.encode(event_state)
        if self.compressor:
            stored_state = self.compressor.compress(stored_state)  # pragma: no cover
        if self.cipher:
            stored_state = self.cipher.encrypt(stored_state)  # pragma: no cover
        return StoredEvent(
            originator_id=domain_event.originator_id,
            originator_version=domain_event.originator_version,
            topic=topic,
            state=stored_state,
        )

    def to_domain_event(self, stored: StoredEvent) -> OriginatorIDVersionProtocol:
        stored_state = stored.state
        if self.cipher:
            stored_state = self.cipher.decrypt(stored_state)  # pragma: no cover
        if self.compressor:
            stored_state = self.compressor.decompress(stored_state)  # pragma: no cover
        event_state: Dict[str, Any] = self.transcoder.decode(stored_state)
        cls = resolve_topic(stored.topic)
        return cls(**event_state)


class OrjsonTranscoder(Transcoder):
    def encode(self, obj: Any) -> bytes:
        return orjson.dumps(obj)

    def decode(self, data: bytes) -> Any:
        return orjson.loads(data)

    def register(self, transcoding: Transcoding) -> None:
        raise ProgrammingError("Please use Pydantic BaseModel")  # pragma: no cover
