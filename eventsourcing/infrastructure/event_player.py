from functools import reduce

import six

from eventsourcing.domain.model.entity import make_stored_entity_id, EventSourcedEntity
from eventsourcing.domain.model.snapshot import take_snapshot
from eventsourcing.domain.services.snapshot import get_snapshot
from eventsourcing.infrastructure.event_store import EventStore
from eventsourcing.infrastructure.stored_events.transcoders import deserialize_domain_entity


class EventPlayer(object):

    def __init__(self, event_store, mutator, domain_class_name=''):
        assert isinstance(event_store, EventStore), event_store
        self.event_store = event_store
        self.mutator = mutator
        self.domain_class_name = domain_class_name

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

        # Get the entity's domain events from the event store.
        since = snapshot.last_event_id if snapshot else None
        events_iterator = self.event_store.get_entity_events(stored_entity_id, since=since)

        # Apply the domain events to the initial state.
        events_iterator = list(events_iterator)
        domain_entity = reduce(self.mutator, events_iterator, initial_state)

        # Raise KeyError when there is no entity (it's either not been created, or it's already discarded).
        if domain_entity is None:
            raise KeyError(entity_id)

        # Create a snapshot if that was too many events to load.
        snapshot_threshold = domain_entity.__class__.snapshot_threshold
        if snapshot_threshold is not None:
            assert isinstance(snapshot_threshold, six.integer_types)

            assert isinstance(domain_entity, EventSourcedEntity)
            version_difference = domain_entity._version - initial_state_version
            if version_difference > snapshot_threshold:
                take_snapshot(domain_entity)

        return domain_entity


def entity_from_snapshot(snapshot):
    return deserialize_domain_entity(snapshot.snapshotted_entity_topic, snapshot.snapshotted_entity_attrs)
