from abc import ABCMeta, abstractmethod, abstractproperty
from eventsourcing.infrastructure.event_player import EventPlayer


class EventSourcedRepository(metaclass=ABCMeta):

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
