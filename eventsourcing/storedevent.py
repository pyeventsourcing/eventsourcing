import uuid

from eventsourcing.utils import ImmutableObject


class StoredEvent(ImmutableObject):
    originator_id: uuid.UUID
    originator_version: int
    topic: str
    state: bytes
