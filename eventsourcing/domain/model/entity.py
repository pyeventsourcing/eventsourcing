from abc import ABCMeta, abstractmethod, abstractstaticmethod
from eventsourcing.domain.model.events import DomainEvent, publish


class EventSourcedEntity(metaclass=ABCMeta):

    class Created(DomainEvent):
        pass

    class Discarded(DomainEvent):
        pass

    def __init__(self, entity_id):
        self._id = entity_id
        self._version = 0
        self._is_discarded = False

    def _increment_version(self):
        self._version += 1

    def _assert_not_discarded(self):
        assert not self._is_discarded

    @property
    def id(self):
        return self._id

    def _validate_originator(self, event):
        assert self.id == event.entity_id
        assert self._version == event.entity_version, "{} != {}".format(self._version, event.entity_version)

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def discard(self):
        self._assert_not_discarded()
        event = self.Discarded(entity_id=self._id, entity_version=self._version)
        self._apply(event)
        publish(event)

    def _apply(self, event):
        assert isinstance(self, EventSourcedEntity)
        self.mutator(self, event)

    @staticmethod
    def mutator(self, event):
        event_type = type(event)
        if event_type == self.Created:
            assert issubclass(self, EventSourcedEntity), self
            self = self(a=event.a, b=event.b, entity_id=event.entity_id)
            self._increment_version()
            return self
        elif event_type == self.Discarded:
            self._validate_originator(event)
            self._is_discarded = True
            self._increment_version()
            return None
        else:
            raise NotImplementedError(repr(event_type))
