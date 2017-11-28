from __future__ import unicode_literals

import hashlib
import json
from abc import ABCMeta, abstractmethod

import six

from eventsourcing.exceptions import DataIntegrityError
from eventsourcing.utils.topic import get_topic, resolve_topic
from eventsourcing.infrastructure.cipher.base import AbstractCipher
from eventsourcing.infrastructure.sequenceditem import SequencedItem, SequencedItemFieldNames
from eventsourcing.utils.transcoding import ObjectJSONDecoder, ObjectJSONEncoder


class AbstractSequencedItemMapper(six.with_metaclass(ABCMeta)):
    @abstractmethod
    def to_sequenced_item(self, domain_event):
        """
        Returns sequenced item for given domain event.
        """

    @abstractmethod
    def from_sequenced_item(self, sequenced_item):
        """
        Return domain event from given sequenced item.
        """


class SequencedItemMapper(AbstractSequencedItemMapper):
    """
    Uses JSON to transcode domain events.
    """

    def __init__(self, sequenced_item_class=SequencedItem, sequence_id_attr_name=None, position_attr_name=None,
                 json_encoder_class=ObjectJSONEncoder, json_decoder_class=ObjectJSONDecoder,
                 always_encrypt=False, cipher=None, other_attr_names=(), with_data_integrity=False):
        self.sequenced_item_class = sequenced_item_class
        self.json_encoder_class = json_encoder_class
        self.json_decoder_class = json_decoder_class
        self.cipher = cipher
        self.always_encrypt = always_encrypt
        self.field_names = SequencedItemFieldNames(self.sequenced_item_class)
        self.sequence_id_attr_name = sequence_id_attr_name or self.field_names.sequence_id
        self.position_attr_name = position_attr_name or self.field_names.position
        self.other_attr_names = other_attr_names or self.field_names[4:]
        self.with_data_integrity = with_data_integrity

    def to_sequenced_item(self, domain_event):
        """
        Constructs a sequenced item from a domain event.
        """
        item_args = self.construct_item_args(domain_event)
        return self.construct_sequenced_item(item_args)

    def construct_item_args(self, domain_event):
        """
        Constructs attributes of a sequenced item from the given domain event.
        """
        # Construct the topic from the event class.
        topic = get_topic(domain_event.__class__)

        # Copy the state of the event.
        event_attrs = domain_event.__dict__.copy()

        # Pop the sequence ID.
        sequence_id = event_attrs.pop(self.sequence_id_attr_name)

        # Pop the position in the sequence.
        position = event_attrs.pop(self.position_attr_name)

        # Decide if this event will be encrypted.
        is_encrypted = self.is_encrypted(domain_event.__class__)

        # Serialise the remaining event attribute values.
        data = self.serialize_event_attrs(event_attrs, is_encrypted=is_encrypted)

        if self.with_data_integrity:
            algorithm = 'sha256'
            hash = self.hash(algorithm, sequence_id, position, data)
            data = '{}:{}:{}'.format(algorithm, hash, data)

        # Get the 'other' args.
        # - these are meant to be derivative of the other attributes,
        #   to populate database fields, and shouldn't affect the hash.
        other_args = tuple((getattr(domain_event, name) for name in self.other_attr_names))

        return (sequence_id, position, topic, data) + other_args

    def hash(self, algorithm, *args):
        if algorithm == 'sha256':
            return hashlib.sha256(self.json_dumps(args).encode()).hexdigest()
        else:
            raise ValueError('Algorithm not supported: {}'.format(algorithm))

    def construct_sequenced_item(self, item_args):
        return self.sequenced_item_class(*item_args)

    def from_sequenced_item(self, sequenced_item):
        """
        Reconstructs domain event from stored event topic and
        event attrs. Used in the event store when getting domain events.
        """
        assert isinstance(sequenced_item, self.sequenced_item_class), (self.sequenced_item_class, type(sequenced_item))

        # Get the domain event class from the topic.
        topic = getattr(sequenced_item, self.field_names.topic)
        domain_event_class = resolve_topic(topic)

        # Deserialize, optionally with decryption.
        is_encrypted = self.is_encrypted(domain_event_class)
        data = getattr(sequenced_item, self.field_names.data)

        hash = None
        algorithm = None
        if self.with_data_integrity:
            try:
                algorithm, hash, data = data.split(':', 2)
            except ValueError:
                raise DataIntegrityError("failed split", sequenced_item[:2])

        event_attrs = self.deserialize_event_attrs(data, is_encrypted)
        sequence_id = getattr(sequenced_item, self.field_names.sequence_id)
        position = getattr(sequenced_item, self.field_names.position)

        if self.with_data_integrity:
            if hash != self.hash(algorithm, sequence_id, position, data):
                raise DataIntegrityError('hash mismatch', sequenced_item[:2])

        # Set the sequence ID and position.
        event_attrs[self.sequence_id_attr_name] = sequence_id
        event_attrs[self.position_attr_name] = position

        # Reconstruct the domain event object.
        return reconstruct_object(domain_event_class, event_attrs)

    def serialize_event_attrs(self, event_attrs, is_encrypted=False):
        event_data = self.json_dumps(event_attrs)
        # Encrypt (optional).
        if is_encrypted:
            assert isinstance(self.cipher, AbstractCipher)
            event_data = self.cipher.encrypt(event_data)

        return event_data

    def json_dumps(self, obj):
        return json.dumps(
            obj,
            separators=(',', ':'),
            sort_keys=True,
            cls=self.json_encoder_class,
        )

    def deserialize_event_attrs(self, event_attrs, is_encrypted):
        """
        Deserialize event attributes from JSON, optionally with decryption.
        """
        if is_encrypted:
            assert isinstance(self.cipher, AbstractCipher), self.cipher
            event_attrs = self.cipher.decrypt(event_attrs)
        return self.json_loads(event_attrs)

    def json_loads(self, s):
        return json.loads(s, cls=self.json_decoder_class)

    def is_encrypted(self, domain_event_class):
        return self.always_encrypt or getattr(domain_event_class, '__always_encrypt__', False)


def reconstruct_object(obj_class, obj_state):
    obj = object.__new__(obj_class)
    obj.__dict__.update(obj_state)
    return obj
