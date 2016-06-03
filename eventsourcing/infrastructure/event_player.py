from functools import reduce

import six

from eventsourcing.domain.model.entity import make_stored_entity_id, EventSourcedEntity
from eventsourcing.domain.model.snapshot import take_snapshot
from eventsourcing.domain.services.snapshot import get_snapshot
from eventsourcing.infrastructure.event_store import EventStore
from eventsourcing.infrastructure.stored_events.transcoders import deserialize_domain_entity


class EventPlayer(object):

    def __init__(self, event_store, domain_class):
        assert isinstance(event_store, EventStore), event_store
        self.event_store = event_store
        self.mutator = domain_class.mutator
        self.domain_class = domain_class
        self.domain_class_name = domain_class.__name__

    def __getitem__(self, entity_id):
        # Make the stored entity ID.
        stored_entity_id = make_stored_entity_id(self.domain_class_name, entity_id)

        # Get snapshot, if exists.
        snapshot = get_snapshot(stored_entity_id, self.event_store)

        # Mutate entity state according to the sequence of domain events.
        initial_state = None if snapshot is None else entity_from_snapshot(snapshot)

        # Remember the version of the initial state (it will change when subsequent events are applied).
        if initial_state is None:
            initial_state_version = 0
        else:
            initial_state_version = initial_state._version

        # Get entity's domain events from event store.
        since = snapshot.last_event_id if snapshot else None
        domain_events = self.event_store.get_entity_events(stored_entity_id, since=since)

        # Get the entity by replaying the entity's domain events.
        # - left fold the domain events over the initial state
        domain_entity = reduce(self.mutator, domain_events, initial_state)

        # Never created or already discarded?
        if domain_entity is None:
            raise KeyError(entity_id)

        # Create a snapshot if that was becoming too many events to load.
        assert isinstance(domain_entity, EventSourcedEntity)
        snapshot_threshold = type(domain_entity).__snapshot_threshold__
        if snapshot_threshold is not None:
            assert isinstance(snapshot_threshold, six.integer_types)
            version_difference = domain_entity._version - initial_state_version
            if version_difference > snapshot_threshold:
                take_snapshot(domain_entity)

        # Return the domain entity.
        return domain_entity


def entity_from_snapshot(snapshot):
    return deserialize_domain_entity(snapshot.snapshotted_entity_topic, snapshot.snapshotted_entity_attrs)
