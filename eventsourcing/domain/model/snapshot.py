from uuid import uuid1

from eventsourcing.domain.model.events import DomainEvent, publish
from eventsourcing.domain.model.example import Example
from eventsourcing.infrastructure.stored_events.transcoders import topic_from_domain_class, make_stored_entity_id


class Snapshot(DomainEvent):

    def __init__(self, entity_id, last_event_id, snapshot_topic, snapshot_attrs):
        super(Snapshot, self).__init__(entity_id=entity_id, entity_version=0, last_event_id=last_event_id,
                                       snapshot_topic=snapshot_topic, snapshot_attrs=snapshot_attrs)

    @property
    def snapshot_topic(self):
        """Path to the class.
        """
        return self.__dict__['snapshot_topic']

    @property
    def snapshot_attrs(self):
        """Attributes of the instance.
        """
        return self.__dict__['snapshot_attrs']


def take_snapshot(entity):
    # Make the 'stored entity ID' for the snapshotted "entity".
    stored_snapshotted_entity_id = make_stored_entity_id(entity.__class__.__name__, entity.id)

    # Create the snapshot event.
    entity_snapshotted = Snapshot(
        entity_id=stored_snapshotted_entity_id,
        last_event_id=uuid1(),
        snapshot_topic=topic_from_domain_class(Example),
        snapshot_attrs=entity.__dict__.copy(),
    )
    publish(entity_snapshotted)

    # Return the event.
    return entity_snapshotted


def make_stored_snapshot_entity_id(stored_entity_id):
    return make_stored_entity_id(Snapshot.__name__, stored_entity_id)
