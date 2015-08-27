from abc import ABCMeta, abstractmethod
from eventsourcing.infrastructure.event_player import EventPlayer


class EventSourcedRepository(metaclass=ABCMeta):

    def __init__(self, event_store):
        self.event_player = self.construct_event_player(event_store)

    def construct_event_player(self, event_store):
        return EventPlayer(event_store=event_store, mutator=self.get_mutator())

    def __contains__(self, item):
        try:
            self.event_player[item]
        except KeyError:
            return False
        else:
            return True

    def __getitem__(self, item):
        return self.event_player[item]

    @abstractmethod
    def get_mutator(self):
        raise NotImplementedError()
