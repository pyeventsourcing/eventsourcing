from abc import ABCMeta, abstractmethod
from copy import deepcopy

import six

from eventsourcing.domain.model.events import publish, resolve_domain_topic, topic_from_domain_class
from eventsourcing.domain.model.snapshot import AbstractSnapshop, Snapshot
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.sequenceditemmapper import reconstruct_object


class AbstractSnapshotStrategy(six.with_metaclass(ABCMeta)):
    @abstractmethod
    def get_snapshot(self, entity_id, lt=None, lte=None):
        """
        Gets the last snapshot for entity, optionally until a particular version number.

        :rtype: Snapshot
        """

    @abstractmethod
    def take_snapshot(self, entity_id, entity, last_event_version):
        """
        Takes a snapshot of entity, using given ID, state and version number.
        
        :rtype: AbstractSnapshop
        """


class EventSourcedSnapshotStrategy(AbstractSnapshotStrategy):
    """Snapshot strategy that uses an event sourced snapshot.
    """

    def __init__(self, event_store):
        assert isinstance(event_store, EventStore)
        self.event_store = event_store

    def get_snapshot(self, entity_id, lt=None, lte=None):
        """
        Gets the last snapshot for entity, optionally until a particular version number.

        :rtype: Snapshot
        """
        snapshots = self.event_store.get_domain_events(entity_id, lt=lt, lte=lte, limit=1, is_ascending=False)
        if len(snapshots) == 1:
            return snapshots[0]

    def take_snapshot(self, entity_id, entity, last_event_version):
        """
        Takes a snapshot by instantiating and publishing a Snapshot domain event.

        :rtype: Snapshot
        """
        # Create the snapshot event.
        snapshot = Snapshot(
            originator_id=entity_id,
            originator_version=last_event_version,
            topic=topic_from_domain_class(entity.__class__),
            state=None if entity is None else deepcopy(entity.__dict__)
        )

        # Publish the snapshot event.
        publish(snapshot)

        # Return the snapshot event.
        return snapshot


def entity_from_snapshot(snapshot):
    """
    Reconstructs domain entity from given snapshot.
    """
    assert isinstance(snapshot, AbstractSnapshop), type(snapshot)
    if snapshot.state is not None:
        entity_class = resolve_domain_topic(snapshot.topic)
        return reconstruct_object(entity_class, snapshot.state)
