from eventsourcing.domain.model.events import DomainEvent


class EventSourcedEntity(object):

    class Created(DomainEvent):
        pass

    class Discarded(DomainEvent):
        pass

    def __init__(self, event):
        self._id = event.entity_id
        self._is_discarded = False
        self._version = event.entity_version

    def _increment_version(self):
        self._version += 1

    @property
    def id(self):
        return self._id

    def _validate_originator(self, event):
        assert self.id == event.entity_id
        assert self._version == event.entity_version, "{} != {}".format(self._version, event.entity_version)

    def _assert_not_discarded(self):
        assert not self._is_discarded

    def __eq__(self, other):
        return self.__dict__ == other.__dict__
