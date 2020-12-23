from functools import reduce
from threading import Lock
from typing import Any, Callable, Dict, Iterable, Optional, Type
from uuid import UUID

from eventsourcing.domain.model.entity import TVersionedEntity, TVersionedEvent
from eventsourcing.domain.model.events import AbstractSnapshot
from eventsourcing.domain.model.repository import AbstractEntityRepository
from eventsourcing.exceptions import RepositoryKeyError
from eventsourcing.infrastructure.base import AbstractEventStore, AbstractRecordManager
from eventsourcing.infrastructure.snapshotting import AbstractSnapshotStrategy
from eventsourcing.whitehead import SEntity


class EventSourcedRepository(
    AbstractEntityRepository[TVersionedEntity, TVersionedEvent]
):
    # The page size by which events are retrieved. If this
    # value is set to a positive integer, the events of
    # the entity will be retrieved in pages, using a series
    # of queries, rather than with one potentially large query.
    __page_size__: Optional[int] = None

    def __init__(
        self,
        event_store: AbstractEventStore,
        use_cache: bool = False,
        snapshot_strategy: Optional[AbstractSnapshotStrategy] = None,
        mutator_func: Optional[
            Callable[
                [Optional[TVersionedEntity], TVersionedEvent],
                Optional[TVersionedEntity],
            ]
        ] = None,
        **kwargs: Any
    ):
        self._event_store: AbstractEventStore = event_store
        self._snapshot_strategy = snapshot_strategy
        self._mutator_func = mutator_func or self.mutate
        super(EventSourcedRepository, self).__init__()

        # NB If you use the cache, make sure to del entities
        # when records fail to write otherwise the cache will
        # give an entity that is ahead of the event records,
        # and writing more records will give a broken sequence.
        self._cache: Dict[UUID, Optional[TVersionedEntity]] = {}
        self._cache_lock = Lock()
        self._use_cache = use_cache

    @property
    def event_store(self) -> AbstractEventStore[TVersionedEvent, AbstractRecordManager]:
        """
        Returns event store object used by this repository.
        """
        return self._event_store

    @property
    def use_cache(self) -> bool:
        return self._use_cache

    @property
    def cache_lock(self) -> Lock:
        return self._cache_lock

    @property
    def cache(self) -> Dict:
        return self._cache

    @use_cache.setter
    def use_cache(self, value: bool) -> None:
        self._use_cache = value
        if not self._use_cache:
            self._cache.clear()

    def __contains__(self, entity_id: UUID) -> bool:
        """
        Returns a boolean value according to whether entity with given ID exists.
        """
        return self.get_entity(entity_id) is not None

    def __getitem__(self, entity_id: UUID) -> TVersionedEntity:
        """
        Returns entity with given ID.

        :param entity_id: ID of entity in the repository.
        :raises RepositoryKeyError: If the entity is not found.
        """
        if self._use_cache:
            try:
                # Get entity from the cache.
                with self._cache_lock:
                    entity: Optional[TVersionedEntity] = self._cache[entity_id]
            except KeyError:
                # Reconstitute the entity.
                entity = self.get_entity(entity_id)
                # Put entity in the cache.
                self.put_entity_in_cache(entity_id, entity)
        else:
            entity = self.get_entity(entity_id)

        # Never created or already discarded?
        if entity is None:
            raise RepositoryKeyError(entity_id)

        # Return entity.
        assert entity is not None
        return entity

    def put_entity_in_cache(self, entity_id: UUID, entity: TVersionedEntity):
        if entity is None or entity_id in self._cache:
            return
        with self._cache_lock:
            self._cache[entity_id] = entity

    def get_entity(
        self, entity_id: UUID, at: Optional[int] = None
    ) -> Optional[TVersionedEntity]:
        """
        Returns entity with given ID, optionally at a version.

        Returns None if entity not found.
        """

        # Get a snapshot (None if none exist).
        if (
            self._snapshot_strategy
            and not self.event_store.record_manager.has_integrated_snapshots
        ):
            snapshot = self._snapshot_strategy.get_snapshot(entity_id, lte=at)
        else:
            snapshot = None

        # Decide the initial state of the entity, and the
        # version of the last item applied to the entity.
        if snapshot is None:
            initial_state = None
            gt = None
        else:
            assert isinstance(snapshot, AbstractSnapshot), snapshot
            initial_state = snapshot.__mutate__(None)
            gt = snapshot.originator_version

        # Obtain and return current state.
        return self.get_and_project_events(
            entity_id, gt=gt, lte=at, initial_state=initial_state
        )

    def get_and_project_events(
        self,
        entity_id: UUID,
        gt: Optional[int] = None,
        gte: Optional[int] = None,
        lt: Optional[int] = None,
        lte: Optional[int] = None,
        limit: Optional[int] = None,
        initial_state: Optional[TVersionedEntity] = None,
        query_descending: bool = False,
    ) -> Optional[TVersionedEntity]:
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
        if (
            gt is None
            and gte is None
            and lt is None
            and lte is None
            and self.__page_size__ is None
        ):
            is_ascending = True
        else:
            is_ascending = not query_descending

        # Get entity's domain events from the event store.
        domain_events = self.event_store.iter_events(
            originator_id=entity_id,
            gt=gt,
            gte=gte,
            lt=lt,
            lte=lte,
            limit=limit,
            is_ascending=is_ascending,
            page_size=self.__page_size__,
        )

        # The events must be replayed in ascending order.
        if not is_ascending:
            domain_events = reversed(list(domain_events))

        # Project the domain events onto the initial state.
        return self.project_events(initial_state, domain_events)

    def project_events(
        self,
        initial_state: Optional[TVersionedEntity],
        domain_events: Iterable[TVersionedEvent],
    ) -> Optional[TVersionedEntity]:
        """
        Evolves initial_state using the domain_events and a mutator function.

        Applies a mutator function cumulatively to a sequence of domain
        events, so as to mutate the initial value to a mutated value.

        This class's mutate() method is used as the default mutator function, but
        custom behaviour can be introduced by passing in a 'mutator_func' argument
        when constructing this class, or by overridding the mutate() method.
        """
        return reduce(self._mutator_func, domain_events, initial_state)

    @staticmethod
    def mutate(
        initial: Optional[TVersionedEntity], event: TVersionedEvent
    ) -> Optional[TVersionedEntity]:
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

    # Todo: Does this method belong on this class?
    def take_snapshot(
        self, entity_id: UUID, lt: Optional[int] = None, lte: Optional[int] = None
    ) -> Optional[AbstractSnapshot]:
        """
        Takes a snapshot of the entity as it existed after the most recent
        event, optionally less than, or less than or equal to, a particular position.
        """
        snapshot = None
        if self._snapshot_strategy:
            if self.event_store.record_manager.has_integrated_snapshots:
                # Get entity.
                entity = self.get_and_project_events(entity_id=entity_id)

                # Take snapshot from entity.
                if entity is not None:
                    snapshot = self._snapshot_strategy.take_snapshot(
                        entity_id, entity, entity.__version__
                    )

            else:
                # Get the latest event (optionally until a particular position).
                latest_event = self.event_store.get_most_recent_event(
                    entity_id, lt=lt, lte=lte
                )

                # If there is something to snapshot, then look for a snapshot
                # taken before or at the entity version of the latest event. Please
                # note, the snapshot might have a smaller version number than
                # the latest event if events occurred since the latest snapshot was taken.
                if latest_event is not None:
                    latest_snapshot = self._snapshot_strategy.get_snapshot(
                        entity_id, lt=lt, lte=lte
                    )
                    latest_version = latest_event.originator_version

                    if (
                        latest_snapshot
                        and latest_snapshot.originator_version == latest_version
                    ):
                        # If up-to-date snapshot exists, there's nothing to do.
                        snapshot = latest_snapshot
                    else:
                        # Otherwise recover entity state from latest snapshot.
                        if latest_snapshot:
                            initial_state = latest_snapshot.__mutate__(None)
                            gt: Optional[int] = latest_snapshot.originator_version
                        else:
                            initial_state = None
                            gt = None

                        # Fast-forward entity state to latest version.
                        entity = self.get_and_project_events(
                            entity_id=entity_id,
                            gt=gt,
                            lte=latest_version,
                            initial_state=initial_state,
                        )

                        # Take snapshot from entity.
                        snapshot = self._snapshot_strategy.take_snapshot(
                            entity_id, entity, latest_version
                        )

        return snapshot

    def get_instance_of(
        self, instance_class: Type[SEntity], entity_id: UUID, at: Optional[int] = None
    ) -> Optional[SEntity]:
        entity = self.get_entity(entity_id, at=at)
        if isinstance(entity, instance_class):
            return entity
        else:
            return None
