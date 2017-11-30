from functools import reduce

from eventsourcing.domain.model.entity import AbstractEventPlayer
from eventsourcing.infrastructure.eventstore import AbstractEventStore


class EventPlayer(AbstractEventPlayer):
    # The page size by which events are retrieved. If this
    # value is set to a positive integer, the events of
    # the entity will be retrieved in pages, using a series
    # of queries, rather than with one potentially large query.
    __page_size__ = None

    def __init__(self, event_store, mutator=None,
                 snapshot_strategy=None, use_cache=False, *args, **kwargs):
        super(EventPlayer, self).__init__(*args, **kwargs)
        # Check we got an event store.
        assert isinstance(event_store, AbstractEventStore), type(event_store)
        self._event_store = event_store
        self._mutator = mutator
        self._snapshot_strategy = snapshot_strategy
        self._cache = {}
        self._use_cache = use_cache

    @property
    def event_store(self):
        return self._event_store

    def replay_events(self, initial_state, domain_events):
        """
        Evolves initial state using the sequence of domain events and a mutator function.
        """
        return reduce(self._mutator or self.mutate, domain_events, initial_state)

    @staticmethod
    def mutate(initial, event):
        return event.mutate(initial)

# def clone_object(initial_state):
#     initial_state_copy = object.__new__(type(initial_state))
#     initial_state_copy.__dict__.update(deepcopy(initial_state.__dict__))
#     return initial_state_copy
