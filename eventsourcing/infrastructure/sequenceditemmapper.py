from __future__ import unicode_literals

from abc import ABCMeta, abstractmethod

import six

from eventsourcing.infrastructure.sequenceditem import SequencedItem, SequencedItemFieldNames
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
                 json_encoder_class=None, json_decoder_class=None, cipher=None, other_attr_names=()):
        self.sequenced_item_class = sequenced_item_class
        self.json_encoder_class = json_encoder_class or ObjectJSONEncoder
        self.json_decoder_class = json_decoder_class or ObjectJSONDecoder
        self.cipher = cipher
        self.field_names = SequencedItemFieldNames(self.sequenced_item_class)
        self.sequence_id_attr_name = sequence_id_attr_name or self.field_names.sequence_id
        self.position_attr_name = position_attr_name or self.field_names.position
        self.other_attr_names = other_attr_names or self.field_names.other_names

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
        sequence_id = event_attrs.get(self.sequence_id_attr_name)

        # Get the position in the sequence.
        position = event_attrs.get(self.position_attr_name)

        # Get the topic from the event attrs, otherwise from the class.
        topic = get_topic(domain_event.__class__)

        # Serialise the remaining event attribute values.
        data = json_dumps(event_attrs, cls=self.json_encoder_class)

        # Encrypt (optional).
        if self.cipher:
            data = self.cipher.encrypt(data)

        # Get the 'other' args.
        # - these are meant to be derivative of the other attributes,
        #   to populate database fields, and shouldn't affect the hash.
        other_args = tuple((getattr(domain_event, name) for name in self.other_attr_names))

        return (sequence_id, position, topic, data) + other_args

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

        # Get the topic and data.
        topic = getattr(sequenced_item, self.field_names.topic)
        data = getattr(sequenced_item, self.field_names.data)

        return self.from_topic_and_data(topic, data)

    def from_topic_and_data(self, topic, data):
        # Decrypt (optional).
        if self.cipher:
            data = self.cipher.decrypt(data)

        # Deserialize.
        event_attrs = json_loads(data, cls=self.json_decoder_class)

        # Resolve topic to event class.
        domain_event_class = resolve_topic(topic)

        # Reconstruct the domain event object.
        return reconstruct_object(domain_event_class, event_attrs)


def reconstruct_object(obj_class, obj_state):
    obj = object.__new__(obj_class)
    obj.__dict__.update(obj_state)
    return obj
