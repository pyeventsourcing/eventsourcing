from abc import ABCMeta, abstractproperty

import six

from eventsourcing.domain.model.events import DomainEvent, publish
from eventsourcing.infrastructure.stored_events.transcoders import topic_from_domain_class, make_stored_entity_id, \
    id_prefix_from_entity


class AbstractSnapshop(six.with_metaclass(ABCMeta)):

    @abstractproperty
    def topic(self):
        """Path to the class.
        """

    @abstractproperty
    def attrs(self):
        """Attributes of the instance.
        """

    @abstractproperty
    def at_event_id(self):
        """Last domain event ID that was applied to the snapshotted entity.
        """


class Snapshot(DomainEvent, AbstractSnapshop):

    def __init__(self, entity_id, topic, attrs, domain_event_id):
        super(Snapshot, self).__init__(entity_id=entity_id, topic=topic, attrs=attrs, domain_event_id=domain_event_id,
                                       entity_version=None)

    @property
    def topic(self):
        """Path to the class.
        """
        return self.__dict__['topic']

    @property
    def attrs(self):
        """Attributes of the instance.
        """
        return self.__dict__['attrs']

    @property
    def at_event_id(self):
        return self.__dict__['domain_event_id']


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
