from functools import reduce
from eventsourcing.infrastructure.event_store import EventStore
from eventsourcing.infrastructure.stored_events import recreate_domain_event


class EventPlayer(object):

    def __init__(self, event_store, domain_class):
        assert isinstance(event_store, EventStore)
        self.event_store = event_store
        self.domain_class = domain_class

    def __getitem__(self, item):
        stored_events = self.event_store.stored_event_repo.get_entity_events(item)
        entity = reduce(self.domain_class.mutator, map(recreate_domain_event, stored_events), self.domain_class)
        if entity is None:
            raise KeyError
        elif entity is self.domain_class:
            raise KeyError
        else:
            return entity
