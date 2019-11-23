from functools import reduce
from types import FunctionType
from typing import Optional

from eventsourcing.infrastructure.snapshotting import AbstractSnapshotStrategy
from eventsourcing.whitehead import TEntity, TEvent
from eventsourcing.infrastructure.base import AbstractEventStore, AbstractEventPlayer


class EventPlayer(AbstractEventPlayer[TEntity, TEvent]):
    # The page size by which events are retrieved. If this
    # value is set to a positive integer, the events of
    # the entity will be retrieved in pages, using a series
    # of queries, rather than with one potentially large query.
    __page_size__: Optional[int] = None

    def __init__(
        self,
        event_store: AbstractEventStore,
        snapshot_strategy: Optional[AbstractSnapshotStrategy] = None,
        mutator_func: Optional[FunctionType] = None,
    ):
        super(EventPlayer, self).__init__()
        # Check we got an event store.
        assert isinstance(event_store, AbstractEventStore), type(event_store)
        self._event_store: AbstractEventStore = event_store
        self._snapshot_strategy = snapshot_strategy
        self._mutator_func = mutator_func

    @property
    def event_store(self) -> AbstractEventStore:
        return self._event_store

    def project_events(self, initial_state, domain_events) -> Optional[TEntity]:
        """
        Evolves initial_state using the domain_events and a mutator function.

        Applies a mutator function cumulatively to a sequence of domain
        events, so as to mutate the initial value to a mutated value.

        This class's mutate() method is used as the default mutator function, but
        custom behaviour can be introduced by passing in a 'mutator_func' argument
        when constructing this class, or by overridding the mutate() method.
        """
        return reduce(self._mutator_func or self.mutate, domain_events, initial_state)

    @staticmethod
    def mutate(initial, event) -> Optional[TEntity]:
        """
        Default mutator function, which uses __mutate__()
        method on event object to mutate initial state.

        :param initial: Initial state to be mutated by this function.
        :param event: Event that causes the initial state to be mutated.
        :return: Returns the mutated state.
        """
        # Check obj is not None.
        if initial is not None:
            event.__check_obj__(initial)
        return event.__mutate__(initial)


# def clone_object(initial_state):
#     initial_state_copy = object.__new__(type(initial_state))
#     initial_state_copy.__dict__.update(deepcopy(initial_state.__dict__))
#     return initial_state_copy
