from __future__ import unicode_literals

import datetime
import json
from abc import ABCMeta, abstractmethod
from collections import namedtuple
from json.decoder import JSONDecoder
from json.encoder import JSONEncoder

import dateutil.parser
import six

from eventsourcing.domain.model.entity import EventSourcedEntity
from eventsourcing.domain.model.events import DomainEvent, resolve_domain_topic, topic_from_domain_class
from eventsourcing.domain.services.cipher import AbstractCipher

EntityVersion = namedtuple('EntityVersion', ['entity_version_id', 'event_id'])

StoredEvent = namedtuple('StoredEvent', ['event_id', 'stored_entity_id', 'event_topic', 'event_attrs'])


class AbstractSequencedItem(tuple):
    __slots__ = ()


class IntegerSequencedItem(AbstractSequencedItem):
    _fields = ('sequence_id', 'position', 'topic', 'data')

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


class TimeSequencedItem(AbstractSequencedItem):
    _fields = ('sequence_id', 'position', 'topic', 'data')

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


class JSONStoredEventTranscoder(StoredEventTranscoder):
    """
    Encodes domain events as stored events, and decodes stored
    events as domain events.
    """

    def __init__(self, json_encoder_cls=ObjectJSONEncoder, json_decoder_cls=ObjectJSONDecoder,
                 always_encrypt=False, cipher=None, stored_event_cls=StoredEvent):

        self.json_encoder_cls = json_encoder_cls
        self.json_decoder_cls = json_decoder_cls
        self.cipher = cipher
        self.always_encrypt = always_encrypt
        self.stored_event_cls = stored_event_cls

    def serialize(self, domain_event):
        """
        Serializes a domain event into a stored event. Used in stored
        event repositories to represent an instance of any type of
        domain event with a common format that can easily be written
        into its particular database management system.
        """
        assert isinstance(domain_event, DomainEvent)

        # Copy the state of the domain event.
        event_attrs = domain_event.__dict__.copy()

        # Get the domain event ID.
        event_id = event_attrs.pop('domain_event_id')

        # Make stored entity ID and topic.
        stored_entity_id = make_stored_entity_id(id_prefix_from_event(domain_event), domain_event.entity_id)
        event_topic = topic_from_domain_class(type(domain_event))

        # Serialise event attributes to JSON.
        serialized_event_attrs = json.dumps(event_attrs, separators=(',', ':'), sort_keys=True,
                                            cls=self.json_encoder_cls)

        # Encrypt (optional).
        if self.always_encrypt or domain_event.__class__.always_encrypt:
            assert isinstance(self.cipher, AbstractCipher)
            serialized_event_attrs = self.cipher.encrypt(serialized_event_attrs)

        # Return a stored event object (a named tuple, by default).
        return self.stored_event_cls(
            event_id=event_id,
            stored_entity_id=stored_entity_id,
            event_topic=event_topic,
            event_attrs=serialized_event_attrs,
        )

    def deserialize(self, stored_event):
        """
        Recreates original domain event from stored event topic and
        event attrs. Used in the event store when getting domain events.
        """
        assert isinstance(stored_event, self.stored_event_cls)

        # Get the domain event class from the topic.
        event_class = resolve_domain_topic(stored_event.event_topic)

        if not issubclass(event_class, DomainEvent):
            raise ValueError("Event class is not a DomainEvent: {}".format(event_class))

        event_attrs = stored_event.event_attrs

        # Decrypt (optional).
        if self.always_encrypt or event_class.always_encrypt:
            assert isinstance(self.cipher, AbstractCipher), self.cipher
            event_attrs = self.cipher.decrypt(event_attrs)

        # Deserialize event attributes from JSON, optionally decrypted with cipher.
        event_attrs = json.loads(event_attrs, cls=self.json_decoder_cls)

        # Set the domain event ID.
        event_attrs['domain_event_id'] = stored_event.event_id

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
    assert isinstance(domain_entity, EventSourcedEntity)
    return id_prefix_from_entity_class(type(domain_entity))


def id_prefix_from_entity_class(domain_class):
    assert issubclass(domain_class, EventSourcedEntity)
    return domain_class.__name__
