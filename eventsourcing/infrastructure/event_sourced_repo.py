from abc import abstractproperty

from eventsourcing.domain.model.entity import EntityRepository, EventSourcedEntity
from eventsourcing.infrastructure.event_player import EventPlayer
from eventsourcing.infrastructure.stored_events.transcoders import id_prefix_from_entity_class


class EventSourcedRepository(EntityRepository):

    def __init__(self, event_store, use_cache=False):
        id_prefix = id_prefix_from_entity_class(self.domain_class)
        mutate_func = self.domain_class.mutate
        self.event_player = EventPlayer(event_store, id_prefix, mutate_func)
        self._cache = {}
        self._use_cache = use_cache

    @abstractproperty
    def domain_class(self):
        return EventSourcedEntity

    def __contains__(self, entity_id):
        try:
            self.__getitem__(entity_id)
        except KeyError:
            return False
        else:
            return True

    def __getitem__(self, entity_id):
        # Get entity from the cache.
        if self._use_cache:
            try:
                return self._cache[entity_id]
            except KeyError:
                pass

        # Replay domain events.
        entity = self.event_player.replay_events(entity_id)

        # Never created or already discarded?
        if entity is None:
            raise KeyError(entity_id)

        # Put entity in the cache.
        if self._use_cache:
             self._cache[entity_id] = entity

        # Return entity.
        return entity
