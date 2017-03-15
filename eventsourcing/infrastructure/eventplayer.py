from functools import reduce

from copy import deepcopy

from eventsourcing.domain.model.entity import EventSourcedEntity
from eventsourcing.domain.model.snapshot import AbstractSnapshop
from eventsourcing.infrastructure.eventstore import AbstractEventStore
from eventsourcing.infrastructure.new_snapshotting import AbstractSnapshotStrategy, entity_from_snapshot
from eventsourcing.infrastructure.transcoding import make_stored_entity_id


class EventPlayer(object):
    """
    Reconstitutes domain entities from domain events
    retrieved from the event store, optionally with snapshots.
    """

    def __init__(self, event_store, id_prefix, mutate_func, page_size=None, is_short=False, snapshot_strategy=None):
        assert isinstance(event_store, AbstractEventStore), event_store
        if snapshot_strategy is not None:
            assert isinstance(snapshot_strategy, AbstractSnapshotStrategy)
        self.event_store = event_store
        self.id_prefix = id_prefix
        self.mutate_func = mutate_func
        self.page_size = page_size
        self.is_short = is_short
        self.snapshot_strategy = snapshot_strategy

    def replay_entity(self, entity_id, after=None, until=None, limit=None, initial_state=None, query_descending=False):
        """
        Reconstitutes requested domain entity from domain events found in event store.
        """
        # Decide if query is in ascending order.
        #  - A "speed up" for when events are stored in descending order (e.g.
        #  in Cassandra) and it is faster to get them in that order.
        #  - This isn't useful when 'until' or 'after' or 'limit' are set,
        #    because the inclusiveness or exclusiveness of until and after
        #    and the end of the stream that is truncated by limit both depend on
        #    the direction of the query. Also paging backwards isn't useful, because
        #    all the events are needed eventually, so it would probably slow things
        #    down. Paging is intended to support replaying longer event streams, and
        #    only makes sense to work in ascending order.
        if self.is_short and after is None and until is None and self.page_size is None:
            is_ascending = False
        else:
            is_ascending = not query_descending

        # Get the domain events that are to be replayed.
        domain_events = self.get_domain_events(entity_id, after, until, limit, is_ascending)

        # Reverse the events if not already in ascending order.
        if not is_ascending:
            domain_events = reversed(list(domain_events))

        # Clone the initial state, to avoid side effects for the caller.
        if initial_state is None:
            initial_state_copy = None
        else:
            initial_state_copy = object.__new__(type(initial_state))
            initial_state_copy.__dict__.update(initial_state.__dict__)

        # Replay the domain events, starting with the initial state.
        return self.replay_events(initial_state_copy, domain_events)

    def replay_events(self, initial_state, domain_events):
        """
        Mutates initial state using the sequence of domain events.
        """
        return reduce(self.mutate_func, domain_events, initial_state)

    def get_domain_events(self, entity_id, after=None, until=None, limit=None, is_ascending=True):
        """
        Returns domain events for given entity ID.
        """
        # Make the stored entity ID.
        stored_entity_id = self.make_stored_entity_id(entity_id)

        # Get entity's domain events from the event store.
        domain_events = self.event_store.get_domain_events(
            stored_entity_id=stored_entity_id,
            after=after,
            until=until,
            limit=limit,
            page_size=self.page_size,
            is_ascending=is_ascending,
        )
        return domain_events

    def take_snapshot(self, entity_id, until=None):
        """
        Takes a snapshot of the entity as it existed after
        the most recent event, optionally until a given time.
        """
        assert isinstance(self.snapshot_strategy, AbstractSnapshotStrategy)

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
        entity = self.replay_entity(entity_id, after=after_event_id, until=last_event_id, initial_state=initial_state)

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

    def fastforward(self, stale_entity, until=None):
        assert isinstance(stale_entity, EventSourcedEntity)

        # Get the entity version object, which provides the event ID.
        stored_entity_id = self.make_stored_entity_id(stale_entity.id)

        # The last applied event version is the one before the current
        # version number, because each mutator increments the version
        # after an event is applied, and it starts by checking the
        # version number is the same. Hence version of the last applied
        # is the value of the entity's version property minus one.
        last_applied_version_number = stale_entity.version - 1
        last_applied_entity_version = self.event_store.get_entity_version(
            stored_entity_id=stored_entity_id,
            version=last_applied_version_number
        )
        last_applied_event_id = last_applied_entity_version.event_id

        # Replay the events since the entity version.
        fresh_entity = self.replay_entity(
            entity_id=stale_entity.id,
            after=last_applied_event_id,
            until=until,
            initial_state=stale_entity,
        )

        # Return the fresh instance.
        return fresh_entity


def clone_object(initial_state):
    initial_state_copy = object.__new__(type(initial_state))
    initial_state_copy.__dict__.update(deepcopy(initial_state.__dict__))
    return initial_state_copy


class NewEventPlayer(object):
    """
    Reconstitutes domain entities from domain events
    retrieved from the event store, optionally with snapshots.
    """

    def __init__(self, event_store, mutate_func, page_size=None, is_short=False, snapshot_strategy=None):
        assert isinstance(event_store, AbstractEventStore), event_store
        if snapshot_strategy is not None:
            assert isinstance(snapshot_strategy, AbstractSnapshotStrategy), snapshot_strategy
        self.event_store = event_store
        self.mutate_func = mutate_func
        self.page_size = page_size
        self.is_short = is_short
        self.snapshot_strategy = snapshot_strategy

    def replay_entity(self, entity_id, gt=None, gte=None, lt=None, lte=None, limit=None, initial_state=None,
                      query_descending=False):
        """
        Reconstitutes requested domain entity from domain events found in event store.
        """
        # Decide if query is in ascending order.
        #  - A "speed up" for when events are stored in descending order (e.g.
        #  in Cassandra) and it is faster to get them in that order.
        #  - This isn't useful when 'until' or 'after' or 'limit' are set,
        #    because the inclusiveness or exclusiveness of until and after
        #    and the end of the stream that is truncated by limit both depend on
        #    the direction of the query. Also paging backwards isn't useful, because
        #    all the events are needed eventually, so it would probably slow things
        #    down. Paging is intended to support replaying longer event streams, and
        #    only makes sense to work in ascending order.
        if self.is_short and gt is None and gte is None and lt is None and lte is None and self.page_size is None:
            is_ascending = False
        else:
            is_ascending = not query_descending

        # Get the domain events that are to be replayed.
        domain_events = self.get_domain_events(entity_id,
                                               gt=gt,
                                               gte=gte,
                                               lt=lt,
                                               lte=lte,
                                               limit=limit,
                                               is_ascending=is_ascending)

        # The events will be replayed in ascending order.
        if not is_ascending:
            domain_events = reversed(list(domain_events))

        # Replay the domain events, starting with the initial state.
        return self.replay_events(initial_state, domain_events)

    def replay_events(self, initial_state, domain_events):
        """
        Mutates initial state using the sequence of domain events.
        """
        return reduce(self.mutate_func, domain_events, initial_state)

    def get_domain_events(self, entity_id, gt=None, gte=None, lt=None, lte=None, limit=None, is_ascending=True):
        """
        Returns domain events for given entity ID.
        """
        # Get entity's domain events from the event store.
        domain_events = self.event_store.get_domain_events(
            entity_id=entity_id,
            gt=gt,
            gte=gte,
            lt=lt,
            lte=lte,
            limit=limit,
            page_size=self.page_size,
            is_ascending=is_ascending,
        )
        return list(domain_events)

    def take_snapshot(self, entity_id, until=None):
        """
        Takes a snapshot of the entity as it existed after
        the most recent event, optionally until a given time.
        """
        assert isinstance(self.snapshot_strategy, AbstractSnapshotStrategy)

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
        entity = self.replay_entity(entity_id, after=after_event_id, until=last_event_id, initial_state=initial_state)

        # Take a snapshot of the entity.
        return self.snapshot_strategy.take_snapshot(entity, at_event_id=last_event_id)

    def get_snapshot(self, entity_id, lte=None):
        """Uses strategy to get a snapshot of the entity,
        optional as it existed until a given time.
        """
        if self.snapshot_strategy:
            return self.snapshot_strategy.get_snapshot(entity_id, lte=lte)

    def get_most_recent_event(self, entity_id, until=None):
        """Returns the most recent event for the given entity ID.
        """
        return self.event_store.get_most_recent_event(entity_id, until=until)

    def fastforward(self, stale_entity, until=None):
        assert isinstance(stale_entity, EventSourcedEntity)

        # The last applied event version is the one before the current
        # version number, because each mutator increments the version
        # after an event is applied, and it starts by checking the
        # version number is the same. Hence version of the last applied
        # is the value of the entity's version property minus one.
        last_applied_version_number = stale_entity.version - 1
        last_applied_entity_version = self.event_store.get_entity_version(
            stored_entity_id=stored_entity_id,
            version=last_applied_version_number
        )
        last_applied_event_id = last_applied_entity_version.event_id

        # Replay the events since the entity version.
        fresh_entity = self.replay_entity(
            entity_id=stale_entity.id,
            after=last_applied_event_id,
            until=until,
            initial_state=stale_entity,
        )

        # Return the fresh instance.
        return fresh_entity
