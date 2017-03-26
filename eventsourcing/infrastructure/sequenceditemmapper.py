from __future__ import unicode_literals

import datetime
import json
from abc import ABCMeta, abstractmethod
from collections import namedtuple
from json.decoder import JSONDecoder
from json.encoder import JSONEncoder
from uuid import UUID

import dateutil.parser
import six

from eventsourcing.domain.model.events import resolve_domain_topic, topic_from_domain_class
from eventsourcing.domain.services.cipher import AbstractCipher

SequencedItem = namedtuple('SequencedItem', ['sequence_id', 'position', 'topic', 'data'])


class AbstractSequencedItemMapper(six.with_metaclass(ABCMeta)):
    @abstractmethod
    def to_sequenced_item(self, domain_event):
        """Serializes a domain event."""

    @abstractmethod
    def from_sequenced_item(self, serialized_event):
        """Deserializes domain events."""


class ObjectJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return {'ISO8601_datetime': obj.strftime('%Y-%m-%dT%H:%M:%S.%f%z')}
        elif isinstance(obj, datetime.date):
            return {'ISO8601_date': obj.isoformat()}
        elif isinstance(obj, UUID):
            return {'UUID': obj.hex}
        elif hasattr(obj, '__class__') and hasattr(obj, '__dict__'):
            topic = topic_from_domain_class(obj.__class__)
            state = obj.__dict__.copy()
            return {
                '__class__': {
                    'topic': topic,
                    'state': state,
                }
            }

        # Let the base class default method raise the TypeError.
        return JSONEncoder.default(self, obj)


class ObjectJSONDecoder(JSONDecoder):
    def __init__(self, **kwargs):
        super(ObjectJSONDecoder, self).__init__(object_hook=ObjectJSONDecoder.from_jsonable, **kwargs)

    @staticmethod
    def from_jsonable(d):
        if 'ISO8601_datetime' in d:
            return ObjectJSONDecoder._decode_datetime(d)
        elif 'ISO8601_date' in d:
            return ObjectJSONDecoder._decode_date(d)
        elif 'UUID' in d:
            return ObjectJSONDecoder._decode_uuid(d)
        elif '__class__' in d:
            return ObjectJSONDecoder._decode_object(d)
        return d

    @staticmethod
    def _decode_date(d):
        return datetime.datetime.strptime(d['ISO8601_date'], '%Y-%m-%d').date()

    @staticmethod
    def _decode_datetime(d):
        return dateutil.parser.parse(d['ISO8601_datetime'])

    @staticmethod
    def _decode_uuid(d):
        return UUID(d['UUID'])

    @staticmethod
    def _decode_object(d):
        topic = d['__class__']['topic']
        state = d['__class__']['state']
        obj_class = resolve_domain_topic(topic)
        obj = object.__new__(obj_class)
        obj.__dict__.update(state)
        return obj


class SequencedItemMapper(AbstractSequencedItemMapper):
    """
    Uses JSON to transcode domain events.
    """

    def __init__(self, sequence_id_attr_name, position_attr_name,
                 encoder_class=ObjectJSONEncoder, decoder_class=ObjectJSONDecoder,
                 always_encrypt=False, cipher=None,
                 sequenced_item_class=SequencedItem):

        self.sequence_id_attr_name = sequence_id_attr_name
        self.position_attr_name = position_attr_name
        self.json_encoder_class = encoder_class
        self.json_decoder_class = decoder_class
        self.cipher = cipher
        self.always_encrypt = always_encrypt
        self.sequenced_item_class = sequenced_item_class

    @property
    def sequence_id_field_name(self):
        # Sequence ID is assumed to be the first field of a sequenced item.
        return self.field_names[0]

    @property
    def position_field_name(self):
        # Position is assumed to be the second field of a sequenced item.
        return self.field_names[1]

    @property
    def topic_field_name(self):
        # Topic is assumed to be the third field of a sequenced item.
        return self.field_names[2]

    @property
    def data_field_name(self):
        # Data is assumed to be the fourth field of a sequenced item.
        return self.field_names[3]

    @property
    def field_names(self):
        return self.sequenced_item_class._fields

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
        assert isinstance(sequenced_item, self.sequenced_item_class), type(sequenced_item)

        # Get the domain event class from the topic.
        domain_event_class = self.class_from_topic(getattr(sequenced_item, self.topic_field_name))

        # Deserialize, optionally with decryption.
        is_encrypted = self.is_encrypted(domain_event_class)
        event_attrs = self.deserialize_event_attrs(getattr(sequenced_item, self.data_field_name), is_encrypted)

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
