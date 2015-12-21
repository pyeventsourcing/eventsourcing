from abc import abstractproperty
from functools import reduce
from eventsourcing.domain.model.entity import EntityRepository
from eventsourcing.infrastructure.event_store import EventStore


class EventPlayer(object):

    def __init__(self, event_store, mutator, id_prefix=''):
        assert isinstance(event_store, EventStore), event_store
        self.event_store = event_store
        self.mutator = mutator
        self.id_prefix = id_prefix

    def __getitem__(self, entity_id):
        # Get the entity's domain events from the event store.
        stored_entity_id = self.id_prefix + '::' + entity_id
        domain_events = self.event_store.get_entity_events(stored_entity_id)

        # Mutate entity state according to the sequence of domain events.
        entity = reduce(self.mutator, domain_events, None)
        if entity is None:
            # Entity already discarded, or it was never created.
            raise KeyError(entity_id)
        else:
            return entity


class EventSourcedRepository(EntityRepository):

    def __init__(self, event_store, use_cache=False):
        self.event_player = self.construct_event_player(event_store)
        self._cache = {}
        self._use_cache = use_cache

    def construct_event_player(self, event_store):
        return EventPlayer(event_store=event_store, mutator=self.domain_class.mutator,
                           id_prefix=self.domain_class.__name__)

    @abstractproperty
    def domain_class(self):
        """Defines the type of entity available in this repo.
        """

    def __getitem__(self, entity_id):
        if not self._use_cache:
            return self.event_player[entity_id]
        else:
            try:
                return self._cache[entity_id]
            except KeyError:
                entity = self.event_player[entity_id]
                self.add_cache(entity_id, entity)
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
