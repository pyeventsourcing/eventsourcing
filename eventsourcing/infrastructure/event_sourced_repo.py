from abc import ABCMeta, abstractproperty
from functools import reduce
from six import with_metaclass
from eventsourcing.infrastructure.event_store import EventStore
from eventsourcing.infrastructure.stored_events.base import recreate_domain_event


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
