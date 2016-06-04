from uuid import uuid1

from eventsourcing.infrastructure.stored_events.transcoders import make_stored_entity_id
from eventsourcing.domain.model.snapshot import Snapshot
from eventsourcing.infrastructure.event_store import EventStore


def get_snapshot(stored_entity_id, event_store):
    """
    Get the last snapshot for entity.
    :param stored_entity_id:
    :param event_store:
    :rtype: Snapshot
    """
    assert isinstance(event_store, EventStore)
    snapshot_stored_entity_id = make_stored_entity_id(Snapshot.__name__, stored_entity_id)
    return event_store.get_most_recent_event(snapshot_stored_entity_id)
