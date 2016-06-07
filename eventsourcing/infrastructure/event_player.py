from functools import reduce

from eventsourcing.domain.model.snapshot import take_snapshot
from eventsourcing.domain.services.snapshot import get_snapshot
from eventsourcing.infrastructure.event_store import EventStore
from eventsourcing.infrastructure.stored_events.transcoders import deserialize_domain_entity,make_stored_entity_id


class EventPlayer(object):

    def __init__(self, event_store, id_prefix, mutate_func, page_size=None):
        assert isinstance(event_store, EventStore), event_store
        self.event_store = event_store
        self.id_prefix = id_prefix
        self.mutate = mutate_func
        self.page_size = page_size

    def replay_events(self, entity_id, until=None):
        # Make the stored entity ID.
        stored_entity_id = self.make_stored_entity_id(entity_id)

        # Try to get initial state from a snapshot.
        snapshot = get_snapshot(stored_entity_id, self.event_store, until=until)
        initial_state = None if snapshot is None else entity_from_snapshot(snapshot)

        # Decide after when we need to get the events.
        after = snapshot.domain_event_id if snapshot else None

        # Get entity's domain events from the event store.
        domain_events = self.event_store.get_entity_events(
            stored_entity_id=stored_entity_id,
            after=after,
            until=until,
            page_size=self.page_size
        )

        # Mutate initial state using the sequence of domain events.
        domain_entity = reduce(self.mutate, domain_events, initial_state)

        # Return the domain entity.
        return domain_entity

    def get_most_recent_event(self, entity_id, until=None):
        return self.event_store.get_most_recent_event(self.make_stored_entity_id(entity_id), until=until)

    def make_stored_entity_id(self, entity_id):
        return make_stored_entity_id(self.id_prefix, entity_id)

    def take_snapshot(self, entity_id, until=None):
        # Get the most recent event (optionally until a particular time).
        most_recent_event = self.get_most_recent_event(entity_id, until=until)

        # Nothing to snapshot?
        if most_recent_event is None:
            return

        # Nothing happened after last snapshot?
        last_snapshot = self.get_snapshot(entity_id, until=until)
        if last_snapshot and last_snapshot.domain_event_id == most_recent_event.domain_event_id:
            return

        # Get entity in the state after this event was applied.
        entity = self.replay_events(entity_id, until=most_recent_event.domain_event_id)

        # Take a snapshot of the entity exactly when this event was applied.
        return take_snapshot(entity, at_event_id=most_recent_event.domain_event_id)

    def get_snapshot(self, entity_id, until=None):
        stored_entity_id = self.make_stored_entity_id(entity_id=entity_id)
        return get_snapshot(stored_entity_id, self.event_store, until=until)


def entity_from_snapshot(snapshot):
    return deserialize_domain_entity(snapshot.topic, snapshot.attrs)
