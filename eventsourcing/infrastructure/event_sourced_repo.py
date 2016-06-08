from abc import abstractproperty

from eventsourcing.domain.model.entity import EntityRepository, EventSourcedEntity
from eventsourcing.infrastructure.event_player import EventPlayer, entity_from_snapshot
from eventsourcing.infrastructure.event_store import EventStore
from eventsourcing.infrastructure.stored_events.transcoders import id_prefix_from_entity_class


class EventSourcedRepository(EntityRepository):

    def __init__(self, event_store, use_cache=False):
        assert isinstance(event_store, EventStore)
        self.event_store = event_store
        domain_class = self.domain_class
        assert issubclass(domain_class, EventSourcedEntity)
        self.event_player = EventPlayer(
            event_store=event_store,
            id_prefix=id_prefix_from_entity_class(domain_class),
            mutate_func=domain_class.mutate,
            page_size=domain_class.__page_size__
        )
        self._cache = {}
        self._use_cache = use_cache

    @abstractproperty
    def domain_class(self):
        """
        Returns the type of entity held by this repository.
        """

    def __contains__(self, entity_id):
        """
        Returns a boolean value according to whether or the entity with given ID exists.
        """
        try:
            self.__getitem__(entity_id)
        except KeyError:
            return False
        else:
            return True

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
            raise KeyError(entity_id)

        # Put entity in the cache.
        if self._use_cache:
             self._cache[entity_id] = entity

        # Return entity.
        return entity

    def get_entity(self, entity_id, until=None):
        """
        Returns entity with given ID, optionally as it was at the given time.
        """
        # Try to get initial state from a snapshot.
        snapshot = self.get_snapshot(entity_id, until)
        initial_state = None if snapshot is None else entity_from_snapshot(snapshot)

        # Decide after when we need to get the events.
        after = snapshot.domain_event_id if snapshot else None

        # Replay domain events.
        return self.event_player.replay_events(entity_id, after=after, until=until, initial_state=initial_state)

    def take_snapshot(self, entity_id, until=None):
        """
        Takes a snapshot of the entity as it existed after the most recent event, optionally until a given time.

        Delegates to the event player.
        """
        return self.event_player.take_snapshot(entity_id, until=until)

    def get_snapshot(self, entity_id, until=None):
        """
        Returns a snapshot of the entity, optionally as it existed until a given time.

        Delegates to the event player.
        """
        return self.event_player.get_snapshot(entity_id, until=until)
