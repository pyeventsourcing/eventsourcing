from __future__ import unicode_literals

import datetime
import json
from abc import ABCMeta, abstractmethod
from collections import namedtuple
from json.decoder import JSONDecoder
from json.encoder import JSONEncoder

import dateutil.parser
import six

from eventsourcing.domain.model.entity import TimestampedVersionedEntity
from eventsourcing.domain.model.events import DomainEvent, resolve_domain_topic, \
    topic_from_domain_class, EntityEvent
from eventsourcing.domain.services.cipher import AbstractCipher

EntityVersion = namedtuple('EntityVersion', ['entity_version_id', 'event_id'])

StoredEvent = namedtuple('StoredEvent', ['event_id', 'entity_id', 'event_topic', 'event_attrs'])


class SequencedItem(tuple):
    __slots__ = ()

    _fields = ('sequence_id', 'position', 'topic', 'data')

    # noinspection PyInitNewSignature
    def __new__(cls, sequence_id, position, topic, data):
        return tuple.__new__(cls, (sequence_id, position, topic, data))

    @property
    def sequence_id(self):
        return self[0]

    @property
    def position(self):
        return self[1]

    @property
    def topic(self):
        return self[2]

    @property
    def data(self):
        return self[3]


class StoredEventTranscoder(six.with_metaclass(ABCMeta)):
    @abstractmethod
    def serialize(self, domain_event):
        """Returns a stored event, for the given domain event."""

    @abstractmethod
    def deserialize(self, stored_event):
        """Returns a domain event, for the given stored event."""


class AbstractSequencedItemMapper(six.with_metaclass(ABCMeta)):
    @abstractmethod
    def to_sequenced_item(self, domain_event):
        """Serializes a domain event."""

    @abstractmethod
    def from_sequenced_item(self, serialized_event):
        """Deserializes domain events."""


# Todo: Reimplement the object encoding and decoding, this time under test.
class ObjectJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return {'ISO8601_datetime': obj.strftime('%Y-%m-%dT%H:%M:%S.%f%z')}
        elif isinstance(obj, datetime.date):
            return {'ISO8601_date': obj.isoformat()}
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
        return d

    @staticmethod
    def _decode_date(d):
        return datetime.datetime.strptime(d['ISO8601_date'], '%Y-%m-%d').date()

    @staticmethod
    def _decode_datetime(d):
        return dateutil.parser.parse(d['ISO8601_datetime'])


class SequencedItemMapper(AbstractSequencedItemMapper):
    """
    Uses JSON to transcode domain events.
    """

    def __init__(self, position_attr_name, encoder_class=ObjectJSONEncoder, decoder_class=ObjectJSONDecoder,
                 always_encrypt=False, cipher=None, sequenced_item_class=SequencedItem):

        self.position_attr_name = position_attr_name
        self.json_encoder_class = encoder_class
        self.json_decoder_class = decoder_class
        self.cipher = cipher
        self.always_encrypt = always_encrypt
        self.sequenced_item_class = sequenced_item_class

    def to_sequenced_item(self, domain_event):
        """
        Serializes a domain event into a stored event. Used in stored
        event repositories to represent an instance of any type of
        domain event with a common format that can easily be written
        into its particular database management system.
        """
        assert isinstance(domain_event, EntityEvent), type(domain_event)

        # Copy the state of the domain event.
        event_attrs = domain_event.__dict__.copy()

        # Pick out the attributes of a sequenced item.
        sequence_id = domain_event.entity_id
        position = event_attrs[self.position_attr_name]
        topic = topic_from_domain_class(type(domain_event))

        # Serialise event attributes to JSON.
        event_data = json.dumps(
            event_attrs,
            separators=(',', ':'),
            sort_keys=True,
            cls=self.json_encoder_class,
        )

        # Encrypt (optional).
        if self.always_encrypt or domain_event.__class__.__always_encrypt__:
            assert isinstance(self.cipher, AbstractCipher)
            event_data = self.cipher.encrypt(event_data)

        # Return a sequenced item.
        sequenced_item = self.sequenced_item_class(
            sequence_id=sequence_id,
            position=position,
            topic=topic,
            data=event_data,
        )
        return sequenced_item

    def from_sequenced_item(self, sequenced_item):
        """
        Recreates original domain event from stored event topic and
        event attrs. Used in the event store when getting domain events.
        """
        assert isinstance(sequenced_item, self.sequenced_item_class)

        # Get the domain event class from the topic.
        event_class = resolve_domain_topic(sequenced_item.topic)

        if not issubclass(event_class, DomainEvent):
            raise ValueError("Event class is not a OldDomainEvent: {}".format(event_class))

        event_attrs = sequenced_item.data

        # Decrypt (optional).
        if self.always_encrypt or event_class.__always_encrypt__:
            assert isinstance(self.cipher, AbstractCipher), self.cipher
            event_attrs = self.cipher.decrypt(event_attrs)

        # Deserialize event attributes from JSON, optionally decrypted with cipher.
        event_attrs = json.loads(event_attrs, cls=self.json_decoder_class)

        # Reinstantiate and return the domain event object.
        domain_event = object.__new__(event_class)
        domain_event.__dict__.update(event_attrs)
        return domain_event


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


def make_stored_entity_id(id_prefix, entity_id):
    return '{}::{}'.format(id_prefix, entity_id)


def id_prefix_from_event(domain_event):
    assert isinstance(domain_event, DomainEvent), type(domain_event)
    return id_prefix_from_event_class(type(domain_event))


def id_prefix_from_event_class(domain_event_class):
    assert issubclass(domain_event_class, DomainEvent), type(domain_event_class)
    return domain_event_class.__qualname__.split('.')[0]


def id_prefix_from_entity(domain_entity):
    assert isinstance(domain_entity, TimestampedVersionedEntity)
    return id_prefix_from_entity_class(type(domain_entity))


def id_prefix_from_entity_class(domain_class):
    assert issubclass(domain_class, TimestampedVersionedEntity), domain_class
    return domain_class.__name__
