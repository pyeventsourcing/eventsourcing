from functools import reduce

from eventsourcing.domain.model.snapshot import AbstractSnapshop
from eventsourcing.infrastructure.event_store import EventStore
from eventsourcing.infrastructure.snapshot_strategy import AbstractSnapshotStrategy
from eventsourcing.infrastructure.stored_events.transcoders import deserialize_domain_entity, make_stored_entity_id


class EventPlayer(object):
    """Reconstitutes domain entities from domain events
    retrieved from the event store, optionally with snapshots.
    """

    def __init__(self, event_store, id_prefix, mutate_func, page_size=None, is_short=False, snapshot_strategy=None):
        assert isinstance(event_store, EventStore), event_store
        if snapshot_strategy is not None:
            assert isinstance(snapshot_strategy, AbstractSnapshotStrategy)
        self.event_store = event_store
        self.id_prefix = id_prefix
        self.mutate_func = mutate_func
        self.page_size = page_size
        self.is_short = is_short
        self.snapshot_strategy = snapshot_strategy

    def replay_events(self, entity_id, after=None, until=None, initial_state=None, query_descending=False):
        """Reconstitutes a domain entity from stored events.
        """

        # Make the stored entity ID.
        stored_entity_id = self.make_stored_entity_id(entity_id)

        if self.is_short and after is None and until is None and self.page_size is None:
            # Speed up for events are stored in descending order (e.g. in Cassandra).
            # - the inclusiveness or exclusiveness of until and after,
            #   and the end of the stream that is limited depends on
            #   query_ascending, so we can't use this method with them
            # - also if there's a page size, it probably isn't short
            is_ascending=False
        else:
            is_ascending = not query_descending

        # Get entity's domain events from the event store.
        domain_events = self.event_store.get_entity_events(
            stored_entity_id=stored_entity_id,
            after=after,
            until=until,
            page_size=self.page_size,
            is_ascending=is_ascending,
        )

        if not is_ascending:
            domain_events = reversed(list(domain_events))

        # Copy initial state, to preserve state of given object.
        if initial_state is not None:
            initial_state_copy = object.__new__(type(initial_state))
            initial_state_copy.__dict__.update(initial_state.__dict__)
            initial_state = initial_state_copy

        # Mutate initial state using the sequence of domain events.
        domain_entity = reduce(self.mutate_func, domain_events, initial_state)

        # Return the resulting domain entity.
        return domain_entity

    def take_snapshot(self, entity_id, until=None):
        """Takes a snapshot of the entity as it existed after
        the most recent event, optionally until a given time.
        """
        if self.snapshot_strategy is None:
            raise ValueError("Can't take snapshots without a snapshot strategy.")

        # Get the last event (optionally until a particular time).
        last_event = self.get_most_recent_event(entity_id, until=until)

        # If there aren't any events, there can't be a snapshot, so return None.
        if last_event is None:
            return None

        # If there is something to snapshot, then look for
        # the last snapshot before the last event.
        last_event_id = last_event.domain_event_id
        last_snapshot = self.get_snapshot(entity_id, until=last_event_id)

        # If there's a snapshot...
        if last_snapshot:
            assert isinstance(last_snapshot, AbstractSnapshop), type(last_snapshot)

            # and it is coincident with the last event...
            if last_snapshot.at_event_id == last_event_id:
                # then there's nothing to do.
                return last_snapshot
            else:
                # Otherwise there must be events after the snapshot, so
                # remember to get events after the last event that was
                # applied to the entity, and obtain the initial entity
                # state so those event can be applied.
                after_event_id = last_snapshot.at_event_id
                initial_state = entity_from_snapshot(last_snapshot)
        else:
            # If there isn't a snapshot, start from scratch.
            after_event_id = None
            initial_state = None

        # Get entity in the state after this event was applied.
        entity = self.replay_events(entity_id, after=after_event_id, until=last_event_id, initial_state=initial_state)

        # Take a snapshot of the entity.
        return self.snapshot_strategy.take_snapshot(entity, at_event_id=last_event_id)

    def get_snapshot(self, entity_id, until=None):
        """Uses strategy to get a snapshot of the entity,
        optional as it existed until a given time.
        """
        if self.snapshot_strategy:
            stored_entity_id = self.make_stored_entity_id(entity_id=entity_id)
            return self.snapshot_strategy.get_snapshot(stored_entity_id, until=until)

    def get_most_recent_event(self, entity_id, until=None):
        """Returns the most recent event for the given entity ID.
        """
        stored_entity_id = self.make_stored_entity_id(entity_id)
        return self.event_store.get_most_recent_event(stored_entity_id, until=until)

    def make_stored_entity_id(self, entity_id):
        """Prefixes the given entity ID with the ID prefix for entity's type.
        """
        return make_stored_entity_id(self.id_prefix, entity_id)


def entity_from_snapshot(snapshot):
    """Deserialises a domain entity from a snapshot object.
    """
    assert isinstance(snapshot, AbstractSnapshop)
    return deserialize_domain_entity(snapshot.topic, snapshot.attrs)
