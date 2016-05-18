from uuid import uuid1

from eventsourcing.domain.model.events import DomainEvent, publish
from eventsourcing.domain.model.example import Example
from eventsourcing.infrastructure.stored_events.transcoders import topic_from_domain_class
from eventsourcing.domain.model.entity import make_stored_entity_id


class EntitySnapshotted(DomainEvent):

    def __init__(self, entity_id, last_event_id, snapshotted_entity_topic, snapshotted_entity_attrs):
        super(EntitySnapshotted, self).__init__(entity_id=entity_id,
                                                last_event_id=last_event_id,
                                                snapshotted_entity_topic=snapshotted_entity_topic,
                                                snapshotted_entity_attrs=snapshotted_entity_attrs,
                                                entity_version=0)

    @property
    def snapshotted_entity_topic(self):
        """Path to the class.
        """
        return self.__dict__['snapshotted_entity_topic']

    @property
    def snapshotted_entity_attrs(self):
        """Attributes of the instance.
        """
        return self.__dict__['snapshotted_entity_attrs']


def take_snapshot(entity):
    # Make the 'stored entity ID' for the snapshotted entity.
    stored_snapshotted_entity_id = make_stored_entity_id(entity.__class__.__name__, entity.id)

    entity_snapshotted = EntitySnapshotted(
        entity_id=stored_snapshotted_entity_id,
        last_event_id=uuid1(),
        snapshotted_entity_topic=topic_from_domain_class(Example),
        snapshotted_entity_attrs=entity.__dict__.copy(),
    )
    publish(entity_snapshotted)

    # Return the event itself (we don't have a mutator for Snapshot entities).
    return entity_snapshotted


def make_stored_snapshot_entity_id(stored_entity_id):
    return make_stored_entity_id(EntitySnapshotted.__name__, stored_entity_id)
