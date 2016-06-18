from eventsourcing.domain.model.snapshot import Snapshot
from eventsourcing.infrastructure.event_store import EventStore
from eventsourcing.infrastructure.stored_events.transcoders import make_stored_entity_id, id_prefix_from_event_class


def get_snapshot(stored_entity_id, event_store, until=None):
    """
    Get the last snapshot for entity.

    :rtype: Snapshot
    """
    assert isinstance(event_store, EventStore)
    snapshot_entity_id = make_stored_entity_id(id_prefix_from_event_class(Snapshot), stored_entity_id)
    return event_store.get_most_recent_event(snapshot_entity_id, until=until)
