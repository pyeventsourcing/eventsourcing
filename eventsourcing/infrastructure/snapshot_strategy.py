from abc import ABCMeta, abstractmethod

import six

from eventsourcing.domain.model.snapshot import take_snapshot
from eventsourcing.domain.services.snapshot import get_snapshot


class AbstractSnapshotStrategy(six.with_metaclass(ABCMeta)):

    @abstractmethod
    def get_snapshot(self, stored_entity_id, until=None):
        """Returns pre-existing snapshot for stored entity ID from given
        event store, optionally until a particular domain event ID.
        """

    @abstractmethod
    def take_snapshot(self, entity, at_event_id):
        """Creates snapshot from given entity, with given domain event ID.
        """


class EventSourcedSnapshotStrategy(AbstractSnapshotStrategy):
    """Snapshot strategy that uses an event sourced snapshot.
    """
    def __init__(self, event_store):
        self.event_store = event_store

    def get_snapshot(self, stored_entity_id, until=None):
        return get_snapshot(stored_entity_id, self.event_store, until=until)

    def take_snapshot(self, entity, at_event_id):
        return take_snapshot(entity=entity, at_event_id=at_event_id)
