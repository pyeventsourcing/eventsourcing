from abc import abstractproperty

from eventsourcing.domain.model.entity import EventSourcedEntity, EntityRepository
from eventsourcing.infrastructure.event_player import EventPlayer


class EventSourcedRepository(EntityRepository):

    def __init__(self, event_store, use_cache=False):
        self.event_player = EventPlayer(event_store, self.domain_class_name, self.domain_class.mutate)
        self._cache = {}
        self._use_cache = use_cache

    @property
    def domain_class_name(self):
        return self.domain_class.__name__

    @property
    def mutate_func(self):
        return self.domain_class.mutate

    @abstractproperty
    def domain_class(self):
        """Defines the type of entity available in this repo.
        """

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
