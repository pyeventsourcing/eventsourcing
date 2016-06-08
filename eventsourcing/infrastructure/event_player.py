from functools import reduce

from eventsourcing.domain.model.snapshot import take_snapshot
from eventsourcing.domain.services.snapshot import get_snapshot
from eventsourcing.infrastructure.event_store import EventStore
from eventsourcing.infrastructure.stored_events.transcoders import deserialize_domain_entity, make_stored_entity_id


class EventPlayer(object):

    def __init__(self, event_store, id_prefix, mutate_func, page_size=None):
        assert isinstance(event_store, EventStore), event_store
        self.event_store = event_store
        self.id_prefix = id_prefix
        self.mutate = mutate_func
        self.page_size = page_size

    def replay_events(self, entity_id, after=None, until=None, initial_state=None):
        # Make the stored entity ID.
        stored_entity_id = self.make_stored_entity_id(entity_id)

        # Get entity's domain events from the event store.
        domain_events = self.event_store.get_entity_events(
            stored_entity_id=stored_entity_id,
            after=after,
            until=until,
            page_size=self.page_size
        )

        # Duplicate initial state, to preserve state of given object.
        if initial_state is not None:
            initial_state_copy = object.__new__(type(initial_state))
            initial_state_copy.__dict__.update(initial_state.__dict__)
            initial_state = initial_state_copy

        # Mutate initial state using the sequence of domain events.
        domain_entity = reduce(self.mutate, domain_events, initial_state)

        # Return the resulting domain entity.
        return domain_entity

    def take_snapshot(self, entity_id, until=None):
        """
        Takes a snapshot of the entity as it existed after the most recent event, optionally until a given time.
        """
        # Get the ultimate event (until a particular time).
        most_recent_event = self.get_most_recent_event(entity_id, until=until)

        # If there isn't any event, there's nothing to snapshot, so return None.
        if most_recent_event is None:
            return None

        until_event_id = most_recent_event.domain_event_id

        # If there is something to snapshot, then get the ultimate snapshot (until a particular time).
        last_snapshot = self.get_snapshot(entity_id, until=until_event_id)

        # If there's a snapshot...
        if last_snapshot:
            if last_snapshot.at_event_id == until_event_id:
                # and it is coincident with the last event, then there's nothing to do.
                return last_snapshot
            else:
                # otherwise there must be events after the snapshot.
                after_event_id = last_snapshot.at_event_id
                initial_state = entity_from_snapshot(last_snapshot)
        else:
            # We need to get all the events (until a particular time) and start from scratch.
            after_event_id = None
            initial_state = None

        # Get entity in the state after this event was applied.
        entity = self.replay_events(entity_id, after=after_event_id, until=until_event_id, initial_state=initial_state)

        # Take a snapshot of the entity exactly when this event was applied.
        return take_snapshot(entity, at_event_id=until_event_id)

    def get_snapshot(self, entity_id, until=None):
        """
        Returns a snapshot of the entity, optional as it existed until a given time.
        """
        stored_entity_id = self.make_stored_entity_id(entity_id=entity_id)
        return get_snapshot(stored_entity_id, self.event_store, until=until)

    def get_most_recent_event(self, entity_id, until=None):
        """
        Returns the most recent event for the given entity ID.
        """
        stored_entity_id = self.make_stored_entity_id(entity_id)
        return self.event_store.get_most_recent_event(stored_entity_id, until=until)

    def make_stored_entity_id(self, entity_id):
        "Prefixes the given entity ID with the ID prefix for entity's type."
        return make_stored_entity_id(self.id_prefix, entity_id)


def entity_from_snapshot(snapshot):
    return deserialize_domain_entity(snapshot.topic, snapshot.attrs)
