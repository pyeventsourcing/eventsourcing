from abc import abstractproperty

from eventsourcing.domain.model.entity import EntityRepository, EventSourcedEntity
from eventsourcing.domain.model.snapshot import take_snapshot
from eventsourcing.infrastructure.event_player import EventPlayer
from eventsourcing.infrastructure.stored_events.transcoders import id_prefix_from_entity_class


class EventSourcedRepository(EntityRepository):

    def __init__(self, event_store, use_cache=False):
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
        entity = self.event_player.replay_events(entity_id)

        # Never created or already discarded?
        if entity is None:
            raise KeyError(entity_id)

        # Put entity in the cache.
        if self._use_cache:
             self._cache[entity_id] = entity

        # Return entity.
        return entity

    def reconstitute_entity(self, entity_id, until=None):
        # Replay domain events.
        return self.event_player.replay_events(entity_id, until=until)

    def take_snapshot(self, entity_id, until=None):
        """
        Takes a snapshot of the entity as it existed the time of the most recent event.
        :param entity_id:
        :return:
        """
        self.event_player.take_snapshot(entity_id, until=until)
