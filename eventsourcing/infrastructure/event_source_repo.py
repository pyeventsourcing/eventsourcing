from abc import abstractproperty, ABCMeta, abstractmethod
from eventsourcing.infrastructure.event_player import EventPlayer


class EventSourcedRepository(metaclass=ABCMeta):

    def __init__(self, event_store):
        # EventPlayer as a delegate, not a super class.
        self.player = EventPlayer(event_store=event_store, mutator=self.get_mutator())

    def __contains__(self, item):
        try:
            self.player[item]
        except KeyError:
            return False
        else:
            return True

    def __getitem__(self, item):
        return self.player[item]

    @abstractmethod
    def get_mutator(self):
        raise NotImplementedError()