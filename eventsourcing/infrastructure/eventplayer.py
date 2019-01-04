from functools import reduce

from eventsourcing.domain.model.entity import AbstractEventPlayer
from eventsourcing.infrastructure.eventstore import AbstractEventStore


class EventPlayer(AbstractEventPlayer):
    # The page size by which events are retrieved. If this
    # value is set to a positive integer, the events of
    # the entity will be retrieved in pages, using a series
    # of queries, rather than with one potentially large query.
    __page_size__ = None

    def __init__(self, event_store, snapshot_strategy=None, use_cache=False, mutator_func=None):
        super(EventPlayer, self).__init__()
        # Check we got an event store.
        assert isinstance(event_store, AbstractEventStore), type(event_store)
        self._event_store = event_store
        self._snapshot_strategy = snapshot_strategy
        self._cache = {}
        # NB If you use the cache, make sure to del entities
        # when records fail to write otherwise the cache will
        # give an entity that is ahead of the event records,
        # and writing more records will give a broken sequence.
        self._use_cache = use_cache
        self._mutator_func = mutator_func

    @property
    def event_store(self):
        return self._event_store

    def project_events(self, initial_state, domain_events):
        """
        Evolves initial state using the sequence of domain events and a mutator function.
        """
        return reduce(self._mutator_func or self.mutate, domain_events, initial_state)

    @staticmethod
    def mutate(initial, event):
        if initial is not None:
            event.__check_obj__(initial)
        return event.__mutate__(initial)

# def clone_object(initial_state):
#     initial_state_copy = object.__new__(type(initial_state))
#     initial_state_copy.__dict__.update(deepcopy(initial_state.__dict__))
#     return initial_state_copy
