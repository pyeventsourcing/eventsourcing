from abc import ABCMeta, abstractmethod

from six import with_metaclass

from eventsourcing.infrastructure.stored_events.transcoders import serialize_domain_event, deserialize_domain_event



class StoredEventRepository(with_metaclass(ABCMeta)):

    serialize_without_json = False

    @abstractmethod
    def append(self, stored_event):
        """Saves given stored event in this repository.
        """

    @abstractmethod
    def __getitem__(self, event_id):
        """Returns stored event for given event ID.
        """

    @abstractmethod
    def __contains__(self, event_id):
        """Tests whether given event ID exists.
        """

    @abstractmethod
    def get_entity_events(self, stored_entity_id):
        """Returns all events for given entity ID.
        """

    @abstractmethod
    def get_topic_events(self, event_topic):
        """Returns all events for given topic.
        """

    def serialize(self, domain_event):
        """Returns a stored event from a domain event.
        """
        return serialize_domain_event(domain_event, without_json=self.serialize_without_json)

    def deserialize(self, stored_event):
        """Returns a domain event from a stored event.
        """
        return deserialize_domain_event(stored_event, without_json=self.serialize_without_json)

