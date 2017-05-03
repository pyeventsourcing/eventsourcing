from functools import reduce

from eventsourcing.infrastructure.eventstore import AbstractEventStore
from eventsourcing.infrastructure.snapshotting import AbstractSnapshotStrategy, entity_from_snapshot


# def clone_object(initial_state):
#     initial_state_copy = object.__new__(type(initial_state))
#     initial_state_copy.__dict__.update(deepcopy(initial_state.__dict__))
#     return initial_state_copy


class EventPlayer(object):
    """
    Reconstitutes domain entities from domain events
    retrieved from the event store, optionally with snapshots.
    """

    def __init__(self, event_store, mutator, page_size=None, is_short=False, snapshot_strategy=None):
        assert isinstance(event_store, AbstractEventStore), event_store
        if snapshot_strategy is not None:
            assert isinstance(snapshot_strategy, AbstractSnapshotStrategy), snapshot_strategy
        self.event_store = event_store
        self.mutator = mutator
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
                                               is_ascending=is_ascending
                                               )

        # The events will be replayed in ascending order.
        if not is_ascending:
            domain_events = reversed(list(domain_events))

        # Replay the domain events, starting with the initial state.
        return self.replay_events(initial_state, domain_events)

    def replay_events(self, initial_state, domain_events):
        """
        Mutates initial state using the sequence of domain events.
        """
        return reduce(self.mutator, domain_events, initial_state)

    def get_domain_events(self, entity_id, gt=None, gte=None, lt=None, lte=None, limit=None, is_ascending=True):
        """
        Returns domain events for given entity ID.
        """
        # Get entity's domain events from the event store.
        domain_events = self.event_store.get_domain_events(originator_id=entity_id, gt=gt, gte=gte, lt=lt, lte=lte,
                                                           limit=limit, is_ascending=is_ascending,
                                                           page_size=self.page_size)
        return domain_events

    def take_snapshot(self, entity_id, lt=None, lte=None):
        """
        Takes a snapshot of the entity as it existed after the most recent
        event, optionally less than, or less than or equal to, a particular position.
        """
        assert isinstance(self.snapshot_strategy, AbstractSnapshotStrategy)

        # Get the last event (optionally until a particular position).
        last_event = self.get_most_recent_event(entity_id, lt=lt, lte=lte)

        if last_event is None:
            # If there aren't any events, there can't be a snapshot.
            snapshot = None
        else:
            # If there is something to snapshot, then look for a snapshot
            # taken before or at the entity version of the last event. Please
            # note, the snapshot might have a smaller version number than
            # the last event if events occurred since the last snapshot was taken.
            last_version = last_event.originator_version
            last_snapshot = self.get_snapshot(entity_id, lte=last_version)

            if last_snapshot and last_snapshot.originator_version == last_version:
                # If up-to-date snapshot exists, there's nothing to do.
                snapshot = last_snapshot
            else:
                # Otherwise recover entity and take snapshot.
                if last_snapshot:
                    initial_state = entity_from_snapshot(last_snapshot)
                    gt = last_snapshot.originator_version
                else:
                    initial_state = None
                    gt = None
                entity = self.replay_entity(entity_id, gt=gt, lte=last_version, initial_state=initial_state)
                snapshot = self.snapshot_strategy.take_snapshot(entity_id, entity, last_version)

        return snapshot

    def get_snapshot(self, entity_id, lt=None, lte=None):
        """
        Returns a snapshot for given entity ID, according to the snapshot strategy.
        """
        if self.snapshot_strategy:
            return self.snapshot_strategy.get_snapshot(entity_id, lt=lt, lte=lte)

    def get_most_recent_event(self, entity_id, lt=None, lte=None):
        """
        Returns the most recent event for the given entity ID.
        """
        return self.event_store.get_most_recent_event(entity_id, lt=lt, lte=lte)
