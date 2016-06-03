from abc import abstractproperty

from eventsourcing.domain.model.entity import EntityRepository
from eventsourcing.infrastructure.event_player import EventPlayer


class EventSourcedRepository(EntityRepository):

    def __init__(self, event_store, use_cache=False):
        self.event_player = self.construct_event_player(event_store)
        self._cache = {}
        self._use_cache = use_cache

    def construct_event_player(self, event_store):
        return EventPlayer(event_store, self.domain_class)

    @abstractproperty
    def domain_class(self):
        """Defines the type of entity available in this repo.
        """

    def __getitem__(self, entity_id):
        # Try to get the entity from the cache.
        if self._use_cache:
            try:
                return self._cache[entity_id]
            except KeyError:
                pass

        # Try to get the entity by replaying stored events.
        entity = self.event_player[entity_id]

        # Try to put the entity in the cache.
        if self._use_cache:
            self.add_cache(entity_id, entity)

        # Return the entity.
        return entity

    def add_cache(self, entity_id, entity):
        self._cache[entity_id] = entity

    def __contains__(self, entity_id):
        try:
            self[entity_id]
        except KeyError:
            return False
        else:
            return True
