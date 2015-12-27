from abc import ABCMeta, abstractmethod

from six import with_metaclass

from eventsourcing.infrastructure.stored_events.transcoders import serialize_domain_event, deserialize_domain_event


class StoredEventRepository(with_metaclass(ABCMeta)):

    serialize_without_json = False
    serialize_with_uuid1 = False

    def __init__(self, json_encoder_cls=None, json_decoder_cls=None):
        self.json_encoder_cls = json_encoder_cls
        self.json_decoder_cls = json_decoder_cls

    @abstractmethod
    def append(self, stored_event):
        """Saves given stored event in this repository.
        :param stored_event: 
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
        :param stored_entity_id: 
        """

    @abstractmethod
    def get_topic_events(self, event_topic):
        """Returns all events for given topic.
        :param event_topic: 
        """

    def serialize(self, domain_event):
        """Returns a stored event from a domain event.
        :type domain_event: object
        :param domain_event:
        """
        return serialize_domain_event(
            domain_event,
            json_encoder_cls=self.json_encoder_cls,
            without_json=self.serialize_without_json,
            with_uuid1=self.serialize_with_uuid1
        )

    def deserialize(self, stored_event):
        """Returns a domain event from a stored event.
        :type stored_event: object
        """
        return deserialize_domain_event(
            stored_event,
            json_decoder_cls=self.json_decoder_cls,
            without_json=self.serialize_without_json
        )
