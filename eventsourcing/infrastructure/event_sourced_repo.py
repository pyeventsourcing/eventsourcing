from abc import ABCMeta, abstractproperty
from functools import reduce
from six import with_metaclass
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

        # Successively apply the domain events to the entity state.
        entity = reduce(self.mutator, domain_events, None)
        if entity is None:
            # Either entity was not created, or it was already discarded.
            raise KeyError(entity_id)
        else:
            return entity


class EventSourcedRepository(with_metaclass(ABCMeta)):

    def __init__(self, event_store):
        self.event_player = self.construct_event_player(event_store)

    def construct_event_player(self, event_store):
        return EventPlayer(event_store=event_store, mutator=self.domain_class.mutator, id_prefix=self.domain_class.__name__)

    @abstractproperty
    def domain_class(self):
        """Defines the type of entity available in this repo.
        """

    def __getitem__(self, entity_id):
        return self.event_player[entity_id]

    def __contains__(self, entity_id):
        try:
            self[entity_id]
        except KeyError:
            return False
        else:
            return True
