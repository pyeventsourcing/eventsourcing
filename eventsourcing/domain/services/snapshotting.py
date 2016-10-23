from abc import ABCMeta, abstractmethod

import six

from eventsourcing.domain.model.events import topic_from_domain_class, publish
from eventsourcing.domain.model.snapshot import Snapshot, AbstractSnapshop
from eventsourcing.domain.services.eventstore import AbstractEventStore
from eventsourcing.domain.services.transcoding import make_stored_entity_id, id_prefix_from_event_class, \
    deserialize_domain_entity, id_prefix_from_entity


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


def get_snapshot(stored_entity_id, event_store, until=None):
    """
    Get the last snapshot for entity.

    :rtype: Snapshot
    """
    assert isinstance(event_store, AbstractEventStore)
    snapshot_entity_id = make_stored_entity_id(id_prefix_from_event_class(Snapshot), stored_entity_id)
    return event_store.get_most_recent_event(snapshot_entity_id, until=until)


def entity_from_snapshot(snapshot):
    """Deserialises a domain entity from a snapshot object.
    """
    assert isinstance(snapshot, AbstractSnapshop)
    return deserialize_domain_entity(snapshot.topic, snapshot.attrs)


def take_snapshot(entity, at_event_id):
    # Make the 'stored entity ID' for the entity, it is used as the Snapshot 'entity ID'.
    id_prefix = id_prefix_from_entity(entity)
    stored_entity_id = make_stored_entity_id(id_prefix, entity.id)

    # Create the snapshot event.
    snapshot = Snapshot(
        entity_id=stored_entity_id,
        domain_event_id=at_event_id,
        topic=topic_from_domain_class(entity.__class__),
        attrs=entity.__dict__.copy(),
    )
    publish(snapshot)

    # Return the event.
    return snapshot
