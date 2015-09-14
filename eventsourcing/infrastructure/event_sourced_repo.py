from abc import ABCMeta, abstractproperty
from functools import reduce
from six import with_metaclass
from eventsourcing.domain.model.entity import EventSourcedEntity
from eventsourcing.infrastructure.event_store import EventStore
from eventsourcing.infrastructure.stored_events.base import recreate_domain_event


class EventPlayer(object):

    def __init__(self, event_store, domain_class):
        assert isinstance(event_store, EventStore), event_store
        assert issubclass(domain_class, EventSourcedEntity), domain_class
        self.event_store = event_store
        self.domain_class = domain_class

    def __getitem__(self, entity_id):
        # Get the stored events from the event store.
        stored_entity_id = self.domain_class.prefix_id(entity_id)
        stored_events = self.event_store.stored_event_repo.get_entity_events(stored_entity_id=stored_entity_id)

        # Recreate the domain events from the stored events.
        domain_events = map(recreate_domain_event, stored_events)

        # Apply the domain events in order to the initial state.
        entity = reduce(self.domain_class.mutator, domain_events, self.domain_class)
        if entity is self.domain_class or entity is None:
            # Either entity was not created, or it was already discarded.
            raise KeyError(entity_id)
        else:
            return entity


class EventSourcedRepository(with_metaclass(ABCMeta)):

    def __init__(self, event_store):
        self.event_player = self.construct_event_player(event_store)

    def construct_event_player(self, event_store):
        return EventPlayer(event_store=event_store, domain_class=self.domain_class)

    @abstractproperty
    def domain_class(self):
        """Defines the type of entity available in this repo.
        """

    def __getitem__(self, item):
        return self.event_player[item]

    def __contains__(self, item):
        try:
            self[item]
        except KeyError:
            return False
        else:
            return True
