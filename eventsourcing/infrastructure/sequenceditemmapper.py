from __future__ import unicode_literals

import json
from abc import ABCMeta, abstractmethod

import six

from eventsourcing.domain.model.events import resolve_domain_topic, topic_from_domain_class
from eventsourcing.domain.services.cipher import AbstractCipher
from eventsourcing.infrastructure.sequenceditem import SequencedItemFieldNames
from eventsourcing.infrastructure.transcoding import ObjectJSONDecoder, ObjectJSONEncoder


class AbstractSequencedItemMapper(six.with_metaclass(ABCMeta)):
    @abstractmethod
    def to_sequenced_item(self, domain_event):
        """Serializes a domain event."""

    @abstractmethod
    def from_sequenced_item(self, serialized_event):
        """Deserializes domain events."""


class SequencedItemMapper(AbstractSequencedItemMapper):
    """
    Uses JSON to transcode domain events.
    """

    SEQUENCE_ID_FIELD_INDEX = 0
    POSITION_FIELD_INDEX = 1

    def __init__(self, sequenced_item_class, sequence_id_attr_name=None, position_attr_name=None,
                 json_encoder_class=ObjectJSONEncoder, json_decoder_class=ObjectJSONDecoder,
                 always_encrypt=False, cipher=None):
        self.sequenced_item_class = sequenced_item_class
        self.json_encoder_class = json_encoder_class
        self.json_decoder_class = json_decoder_class
        self.cipher = cipher
        self.always_encrypt = always_encrypt
        self.field_names = SequencedItemFieldNames(self.sequenced_item_class)
        self.sequence_id_attr_name = sequence_id_attr_name or self.field_names[self.SEQUENCE_ID_FIELD_INDEX]
        self.position_attr_name = position_attr_name or self.field_names[self.POSITION_FIELD_INDEX]

    def to_sequenced_item(self, domain_event):
        """
        Constructs a sequenced item from a domain event.
        """
        item_args = self.construct_item_args(domain_event)
        return self.construct_sequenced_item(item_args)

    def construct_item_args(self, domain_event):
        # Construct attributes of a sequenced item from the domain event.

        # Identify the sequence ID.
        sequence_id = getattr(domain_event, self.sequence_id_attr_name)

        # Identify the position in the sequence.
        position = getattr(domain_event, self.position_attr_name)
        topic = self.topic_from_domain_class(domain_event.__class__)

        # Serialise event attributes to JSON, optionally encrypted.
        is_encrypted = self.is_encrypted(domain_event.__class__)
        event_data = self.serialize_event_attrs(domain_event.__dict__, is_encrypted=is_encrypted)

        return (sequence_id, position, topic, event_data)

    def construct_sequenced_item(self, item_args):
        return self.sequenced_item_class(*item_args)

    def from_sequenced_item(self, sequenced_item):
        """
        Reconstructs domain event from stored event topic and
        event attrs. Used in the event store when getting domain events.
        """
        assert isinstance(sequenced_item, self.sequenced_item_class), (self.sequenced_item_class, type(sequenced_item))

        # Get the domain event class from the topic.
        domain_event_class = self.class_from_topic(getattr(sequenced_item, self.field_names.topic))

        # Deserialize, optionally with decryption.
        is_encrypted = self.is_encrypted(domain_event_class)
        event_attrs = self.deserialize_event_attrs(getattr(sequenced_item, self.field_names.data), is_encrypted)

        # Reconstruct the domain event object.
        return self.reconstruct_object(domain_event_class, event_attrs)

    def reconstruct_object(self, obj_class, obj_state):
        obj = object.__new__(obj_class)
        obj.__dict__.update(obj_state)
        return obj

    def topic_from_domain_class(self, domain_class):
        return topic_from_domain_class(domain_class)

    def class_from_topic(self, topic):
        return resolve_domain_topic(topic)

    def serialize_event_attrs(self, event_attrs, is_encrypted=False):
        event_data = json.dumps(
            event_attrs,
            separators=(',', ':'),
            sort_keys=True,
            cls=self.json_encoder_class,
        )
        # Encrypt (optional).
        if is_encrypted:
            assert isinstance(self.cipher, AbstractCipher)
            event_data = self.cipher.encrypt(event_data)

        return event_data

    def deserialize_event_attrs(self, event_attrs, is_encrypted):
        """
        Deserialize event attributes from JSON, optionally with decryption.
        """
        if is_encrypted:
            assert isinstance(self.cipher, AbstractCipher), self.cipher
            event_attrs = self.cipher.decrypt(event_attrs)
        return json.loads(event_attrs, cls=self.json_decoder_class)

    def is_encrypted(self, domain_event_class):
        return self.always_encrypt or getattr(domain_event_class, '__always_encrypt__', False)


def deserialize_domain_entity(entity_topic, entity_attrs):
    """
    Return a new domain entity object from a given topic (a string) and attributes (a dict).
    """
    # Get the domain entity class from the entity topic.
    domain_class = resolve_domain_topic(entity_topic)

    # Instantiate the domain entity class.
    entity = object.__new__(domain_class)

    # Set the attributes.
    entity.__dict__.update(entity_attrs)

    # Return a new domain entity object.
    return entity
