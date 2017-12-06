from __future__ import unicode_literals

from abc import ABCMeta, abstractmethod

import six

from eventsourcing.exceptions import DataIntegrityError
from eventsourcing.utils.cipher.base import AbstractCipher
from eventsourcing.infrastructure.sequenceditem import SequencedItem, SequencedItemFieldNames
from eventsourcing.utils.hashing import hash_for_data_integrity
from eventsourcing.utils.topic import get_topic, resolve_topic
from eventsourcing.utils.transcoding import ObjectJSONDecoder, ObjectJSONEncoder, json_dumps, json_loads


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
        self.other_attr_names = other_attr_names or self.field_names[5:]
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
        # Copy the state of the event.
        event_attrs = domain_event.__dict__.copy()

        # Get the sequence ID.
        sequence_id = event_attrs.pop(self.sequence_id_attr_name)

        # Get the position in the sequence.
        position = event_attrs.pop(self.position_attr_name)

        # Get the topic from the event attrs, otherwise from the class.
        topic = get_topic(domain_event.__class__)

        # Serialise the remaining event attribute values.
        data = json_dumps(event_attrs, cls=self.json_encoder_class)

        # Encrypt (optional).
        if self.always_encrypt:
            assert isinstance(self.cipher, AbstractCipher)
            data = self.cipher.encrypt(data)

        # Hash sequence ID, position, topic, and data.
        hash = ''
        if self.with_data_integrity:
            hash = self.hash_for_data_integrity(
                sequence_id, position, topic, data
            )

        # Get the 'other' args.
        # - these are meant to be derivative of the other attributes,
        #   to populate database fields, and shouldn't affect the hash.
        other_args = tuple((getattr(domain_event, name) for name in self.other_attr_names))

        return (sequence_id, position, topic, data, hash) + other_args

    def hash_for_data_integrity(self, sequence_id, position, topic, data):
        obj = (sequence_id, position, topic, data)
        return hash_for_data_integrity(self.json_encoder_class, obj)

    def construct_sequenced_item(self, item_args):
        return self.sequenced_item_class(*item_args)

    def from_sequenced_item(self, sequenced_item):
        """
        Reconstructs domain event from stored event topic and
        event attrs. Used in the event store when getting domain events.
        """
        assert isinstance(sequenced_item, self.sequenced_item_class), (
            self.sequenced_item_class, type(sequenced_item)
        )

        # Get the sequence ID, position, topic, data, and hash.
        sequence_id = getattr(sequenced_item, self.field_names.sequence_id)
        position = getattr(sequenced_item, self.field_names.position)
        topic = getattr(sequenced_item, self.field_names.topic)
        data = getattr(sequenced_item, self.field_names.data)
        hash = getattr(sequenced_item, self.field_names.hash)

        # Check data integrity (optional).
        if self.with_data_integrity:
            expected = self.hash_for_data_integrity(
                sequence_id, position, topic, data
            )
            if hash != expected:
                raise DataIntegrityError(
                    'hash mismatch',
                    sequenced_item.sequence_id,
                    sequenced_item.position
                )

        # Decrypt (optional).
        if self.always_encrypt:
            assert isinstance(self.cipher, AbstractCipher), self.cipher
            data = self.cipher.decrypt(data)

        # Deserialize.
        event_attrs = json_loads(data, cls=self.json_decoder_class)

        # Resolve topic to event class.
        domain_event_class = resolve_topic(topic)

        # Set the sequence ID and position.
        event_attrs[self.sequence_id_attr_name] = sequence_id
        event_attrs[self.position_attr_name] = position

        # Reconstruct the domain event object.
        return reconstruct_object(domain_event_class, event_attrs)


def reconstruct_object(obj_class, obj_state):
    obj = object.__new__(obj_class)
    obj.__dict__.update(obj_state)
    return obj
