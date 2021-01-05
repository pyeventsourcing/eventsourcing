import uuid

from eventsourcing.domain import ImmutableObject


class StoredEvent(ImmutableObject):
    originator_id: uuid.UUID
    originator_version: int
    topic: str
    state: bytes
