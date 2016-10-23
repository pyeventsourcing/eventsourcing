from abc import abstractproperty

from eventsourcing.domain.model.entity import EntityRepository, EventSourcedEntity
from eventsourcing.domain.services.eventplayer import EventPlayer
from eventsourcing.domain.services.eventstore import AbstractEventStore
from eventsourcing.domain.services.snapshotting import entity_from_snapshot
from eventsourcing.domain.services.transcoding import id_prefix_from_entity_class
from eventsourcing.exceptions import RepositoryKeyError


class EventSourcedRepository(EntityRepository):

    # If the entity won't have very many events, marking the entity as
    # "short" by setting __is_short__ value equal to True will mean
    # the fastest path for getting all the events is used. If you set
    # a value for page size (see below), this option will have no effect.
    __is_short__ = False

    # The page size by which events are retrieved. If this
    # value is set to a positive integer, the events of
    # the entity will be retrieved in pages, using a series
    # of queries, rather than with one potentially large query.
    __page_size__ = None

    def __init__(self, event_store, use_cache=False, snapshot_strategy=None):
        self._cache = {}
        self._use_cache = use_cache
        self._snapshot_strategy = snapshot_strategy

        # Check we got an event store.
        assert isinstance(event_store, AbstractEventStore)
        self.event_store = event_store

        # Check domain class is a type of event sourced entity.
        assert issubclass(self.domain_class, EventSourcedEntity)

        # Instantiate an event player for this repo, with
        # repo-specific mutate function, page size, etc.
        self.event_player = EventPlayer(
            event_store=self.event_store,
            id_prefix=id_prefix_from_entity_class(self.domain_class),
            mutate_func=self.domain_class.mutate,
            page_size=self.__page_size__ or self.domain_class.__page_size__,
            is_short=self.__is_short__ or self.domain_class.__is_short__,
            snapshot_strategy=self._snapshot_strategy,
        )

    def __contains__(self, entity_id):
        """
        Returns a boolean value according to whether entity with given ID exists.
        """
        return self.get_entity(entity_id) is not None

    def __getitem__(self, entity_id):
        """
        Returns entity with given ID.
        """
        # Get entity from the cache.
        if self._use_cache:
            try:
                return self._cache[entity_id]
            except KeyError:
                pass

        # Reconstitute the entity.
        entity = self.get_entity(entity_id)

        # Never created or already discarded?
        if entity is None:
            raise RepositoryKeyError(entity_id)

        # Put entity in the cache.
        if self._use_cache:
            self.add_cache(entity_id, entity)

        # Return entity.
        return entity

    def add_cache(self, entity_id, entity):
        self._cache[entity_id] = entity

    @abstractproperty
    def domain_class(self):
        """
        Returns the type of entity held by this repository.
        """
        return EventSourcedEntity

    def get_entity(self, entity_id, until=None):
        """
        Returns entity with given ID, optionally as it was until the given domain event ID.
        """

        # Get a snapshot (None if none exist).
        snapshot = self.event_player.get_snapshot(entity_id, until)

        # Decide the initial state, and after when we need to get the events.
        if snapshot is None:
            after = None
            initial_state = None
        else:
            after = snapshot.at_event_id
            initial_state = entity_from_snapshot(snapshot)

        # Replay domain events.
        return self.event_player.replay_events(entity_id, after=after, until=until, initial_state=initial_state)

    def fastforward(self, stale_entity, until=None):
        """
        Mutates an instance of an entity, according to the events that have occurred since its version.
        """
        return self.event_player.fastforward(stale_entity, until=until)
