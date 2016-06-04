from functools import reduce

import six

from eventsourcing.domain.model.entity import EventSourcedEntity
from eventsourcing.domain.model.snapshot import take_snapshot
from eventsourcing.domain.services.snapshot import get_snapshot
from eventsourcing.infrastructure.event_store import EventStore
from eventsourcing.infrastructure.stored_events.transcoders import deserialize_domain_entity, make_stored_entity_id


class EventPlayer(object):

    def __init__(self, event_store, id_prefix, mutate_func):
        assert isinstance(event_store, EventStore), event_store
        self.event_store = event_store
        self.id_prefix = id_prefix
        self.mutate = mutate_func

    def replay_events(self, entity_id):
        # Make the stored entity ID.
        stored_entity_id = make_stored_entity_id(self.id_prefix, entity_id)

        # Get snapshot, if exists.
        snapshot = get_snapshot(stored_entity_id, self.event_store)

        # Mutate entity state according to the sequence of domain events.
        initial_state = None if snapshot is None else entity_from_snapshot(snapshot)

        # Get the initial version.
        initial_version = 0 if initial_state is None else initial_state._version

        # Decide since when we need to get the events.
        since = snapshot.last_event_id if snapshot else None

        # Get entity's domain events from event store.
        domain_events = self.event_store.get_entity_events(stored_entity_id, since=since)

        # Get the entity by a left fold of the domain events over the initial state.
        domain_entity = reduce(self.mutate, domain_events, initial_state)

        # Take a snapshot if too many versions since the initial version for this type.
        if domain_entity is not None:
            assert isinstance(domain_entity, EventSourcedEntity)
            threshold = domain_entity.__snapshot_threshold__
            if isinstance(threshold, six.integer_types) and threshold >= 0:
                difference = domain_entity.version - initial_version
                if difference > threshold:
                    take_snapshot(domain_entity)

        # Return the domain entity.
        return domain_entity


def entity_from_snapshot(snapshot):
    return deserialize_domain_entity(snapshot.topic, snapshot.attrs)
