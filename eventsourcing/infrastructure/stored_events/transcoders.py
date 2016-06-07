import datetime
import importlib
import json
import uuid
from collections import namedtuple
from uuid import UUID

import dateutil.parser
from six import BytesIO

from eventsourcing.domain.model.entity import EventSourcedEntity
from eventsourcing.domain.model.events import topic_from_domain_class, resolve_domain_topic, resolve_attr, DomainEvent

try:
    import numpy
except:
    numpy = None


def serialize_domain_event(domain_event, json_encoder_cls=None, without_json=False, with_uuid1=False):
    """
    Serializes a domain event into a stored event.
    """
    if json_encoder_cls is None:
        json_encoder_cls = ObjectJSONEncoder
    # assert isinstance(domain_event, DomainEvent)
    if with_uuid1:
        event_id = domain_event.domain_event_id
    else:
        event_id = uuid.uuid4().hex
    stored_entity_id = make_stored_entity_id(id_prefix_from_event(domain_event), domain_event.entity_id)
    event_topic = topic_from_domain_class(domain_event.__class__)
    if without_json:
        event_attrs = domain_event
    else:
        event_attrs = json.dumps(domain_event.__dict__, separators=(',', ':'), sort_keys=True, cls=json_encoder_cls)
    return StoredEvent(
        event_id=event_id,
        stored_entity_id=stored_entity_id,
        event_topic=event_topic,
        event_attrs=event_attrs,
    )


def deserialize_domain_event(stored_event, json_decoder_cls=None, without_json=False):
    """
    Recreates original domain event from stored event topic and event attrs.
    """
    # assert isinstance(stored_event, StoredEvent)
    if json_decoder_cls is None:
        json_decoder_cls = ObjectJSONDecoder
    if without_json:
        domain_event = stored_event.event_attrs
    else:
        event_class = resolve_domain_topic(stored_event.event_topic)
        event_data = json.loads(stored_event.event_attrs, cls=json_decoder_cls)
        try:
            # domain_event = event_class(**event_data)
            # Todo: Remove line above, and this comment, line above is replaced by lines below in this version.
            domain_event = object.__new__(event_class)
            domain_event.__dict__.update(event_data)
        except TypeError:
            raise TypeError("Unable to instantiate class '{}' with data '{}'".format(stored_event.event_topic, stored_event.event_attrs))
    return domain_event


class ObjectJSONEncoder(json.JSONEncoder):

    def default(self, obj):
        try:
            return super(ObjectJSONEncoder, self).default(obj)
        except TypeError as e:
            if "not JSON serializable" not in str(e):
                raise
            if isinstance(obj, datetime.datetime):
                return { 'ISO8601_datetime': obj.strftime('%Y-%m-%dT%H:%M:%S.%f%z') }
            if isinstance(obj, datetime.date):
                return { 'ISO8601_date': obj.isoformat() }
            if numpy is not None and isinstance(obj, numpy.ndarray) and obj.ndim == 1:
                memfile = BytesIO()
                numpy.save(memfile, obj)
                memfile.seek(0)
                serialized = json.dumps(memfile.read().decode('latin-1'))
                d = {
                    '__ndarray__': serialized,
                }
                return d
            else:
                d = {
                    '__class__': obj.__class__.__qualname__,
                    '__module__': obj.__module__,
                }
                return d


class ObjectJSONDecoder(json.JSONDecoder):

    def __init__(self, **kwargs):
        super(ObjectJSONDecoder, self).__init__(object_hook=ObjectJSONDecoder.from_jsonable, **kwargs)

    @staticmethod
    def from_jsonable(d):
        if '__ndarray__' in d:
            return ObjectJSONDecoder._decode_ndarray(d)
        elif '__class__' in d and '__module__' in d:
            return ObjectJSONDecoder._decode_class(d)
        elif 'ISO8601_datetime' in d:
            return ObjectJSONDecoder._decode_datetime(d)
        elif 'ISO8601_date' in d:
            return ObjectJSONDecoder._decode_date(d)
        return d

    @staticmethod
    def _decode_ndarray(d):
        serialized = d['__ndarray__']
        memfile = BytesIO()
        memfile.write(json.loads(serialized).encode('latin-1'))
        memfile.seek(0)
        return numpy.load(memfile)

        # return numpy.array(obj_data, d['dtype']).reshape(d['shape'])

    @staticmethod
    def _decode_class(d):
        class_name = d.pop('__class__')
        module_name = d.pop('__module__')
        module = importlib.import_module(module_name)
        cls = resolve_attr(module, class_name)
        try:
            obj = cls(**d)
        except Exception:
            obj = cls()
            for attr, value in d.items():
                obj.__dict__[attr] = ObjectJSONDecoder.from_jsonable(value)
        return obj

    @staticmethod
    def _decode_date(d):
        return datetime.datetime.strptime(d['ISO8601_date'], '%Y-%m-%d').date()

    @staticmethod
    def _decode_datetime(d):
        return dateutil.parser.parse(d['ISO8601_datetime'])


StoredEvent = namedtuple('StoredEvent', ['event_id', 'stored_entity_id', 'event_topic', 'event_attrs'])


def deserialize_domain_entity(entity_topic, entity_attrs):
    domain_class = resolve_domain_topic(entity_topic)
    entity = object.__new__(domain_class)
    entity.__dict__.update(**entity_attrs)
    return entity


def make_stored_entity_id(id_prefix, entity_id):
    return id_prefix + '::' + entity_id


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
