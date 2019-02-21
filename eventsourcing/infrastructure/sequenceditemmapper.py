from __future__ import unicode_literals

from abc import ABC, abstractmethod

from eventsourcing.infrastructure.sequenceditem import SequencedItem, SequencedItemFieldNames
from eventsourcing.utils.topic import get_topic, resolve_topic
from eventsourcing.utils.transcoding import ObjectJSONDecoder, ObjectJSONEncoder, json_dumps, json_loads


class AbstractSequencedItemMapper(ABC):
    @abstractmethod
    def item_from_event(self, domain_event):
        """
        Constructs and returns a sequenced item for given domain event.
        """

    @abstractmethod
    def event_from_item(self, sequenced_item):
        """
        Constructs and returns a domain event for given sequenced item.
        """


class SequencedItemMapper(AbstractSequencedItemMapper):
    """
    Uses JSON to transcode domain events.
    """

    def __init__(self, sequenced_item_class=SequencedItem, sequence_id_attr_name=None,
                 position_attr_name=None, json_encoder_class=None, json_decoder_class=None,
                 cipher=None, other_attr_names=()):
        self.sequenced_item_class = sequenced_item_class
        self.json_encoder_class = json_encoder_class or ObjectJSONEncoder
        self.json_decoder_class = json_decoder_class or ObjectJSONDecoder
        self.cipher = cipher
        self.field_names = SequencedItemFieldNames(self.sequenced_item_class)
        self.sequence_id_attr_name = sequence_id_attr_name or self.field_names.sequence_id
        self.position_attr_name = position_attr_name or self.field_names.position
        self.other_attr_names = other_attr_names or self.field_names.other_names

    def item_from_event(self, domain_event):
        """
        Constructs a sequenced item from a domain event.
        """
        item_args = self.construct_item_args(domain_event)
        return self.construct_sequenced_item(item_args)

    def construct_item_args(self, domain_event):
        """
        Constructs attributes of a sequenced item from the given domain event.
        """
        # Get the sequence ID.
        sequence_id = domain_event.__dict__[self.sequence_id_attr_name]

        # Get the position in the sequence.
        position = getattr(domain_event, self.position_attr_name, None)

        # Get topic and data.
        topic, state = self.get_item_topic_and_state(
            domain_event.__class__,
            domain_event.__dict__
        )

        # Get the 'other' args.
        # - these are meant to be derivative of the other attributes,
        #   to populate database fields, and shouldn't affect the hash.
        other_args = tuple((getattr(domain_event, name) for name in self.other_attr_names))

        return (sequence_id, position, topic, state) + other_args

    def get_item_topic_and_state(self, domain_event_class, event_attrs):
        # Get the topic from the event attrs, otherwise from the class.
        topic = get_topic(domain_event_class)

        # Serialise the event attributes.
        state = json_dumps(event_attrs, cls=self.json_encoder_class)

        # Encrypt serialised state.
        if self.cipher:
            state = self.cipher.encrypt(state)

        return topic, state

    def construct_sequenced_item(self, item_args):
        return self.sequenced_item_class(*item_args)

    def event_from_item(self, sequenced_item):
        """
        Reconstructs domain event from stored event topic and
        event attrs. Used in the event store when getting domain events.
        """
        assert isinstance(sequenced_item, self.sequenced_item_class), (
            self.sequenced_item_class, type(sequenced_item)
        )

        # Get the topic and state.
        topic = getattr(sequenced_item, self.field_names.topic)
        state = getattr(sequenced_item, self.field_names.state)

        return self.event_from_topic_and_state(topic, state)

    def event_from_topic_and_state(self, topic, state):
        domain_event_class, event_attrs = self.get_event_class_and_attrs(topic, state)

        # Reconstruct domain event object.
        return reconstruct_object(domain_event_class, event_attrs)

    def get_event_class_and_attrs(self, topic, state):
        # Resolve topic to event class.
        domain_event_class = resolve_topic(topic)

        # Decrypt state.
        if self.cipher:
            state = self.cipher.decrypt(state)

        # Deserialize data.
        event_attrs = json_loads(state, cls=self.json_decoder_class)
        return domain_event_class, event_attrs


def reconstruct_object(obj_class, obj_state):
    obj = object.__new__(obj_class)
    obj.__dict__.update(obj_state)
    return obj
