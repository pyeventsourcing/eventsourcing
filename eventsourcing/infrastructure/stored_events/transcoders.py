import datetime
import importlib
import json
import uuid
from collections import namedtuple

import dateutil.parser
import numpy
from six import BytesIO

from eventsourcing.exceptions import TopicResolutionError


def serialize_domain_event(domain_event, without_json=False, with_uuid1=False):
    """
    Serializes a domain event into a stored event.
    """
    # assert isinstance(domain_event, DomainEvent)
    if with_uuid1:
        event_id = uuid.uuid1().hex
    else:
        event_id = uuid.uuid4().hex
    stored_entity_id = entity_class_name_from_domain_event(domain_event) + '::' + domain_event.entity_id
    event_topic = topic_from_domain_event(domain_event)
    if without_json:
        event_attrs = domain_event
    else:
        event_attrs = json.dumps(domain_event.__dict__, separators=(',', ':'), sort_keys=True, cls=ObjectJSONEncoder)
    return StoredEvent(
        event_id=event_id,
        stored_entity_id=stored_entity_id,
        event_topic=event_topic,
        event_attrs=event_attrs,
    )


def deserialize_domain_event(stored_event, without_json=False):
    """
    Recreates original domain event from stored event topic and event attrs.
    """
    # assert isinstance(stored_event, StoredEvent)
    if without_json:
        domain_event = stored_event.event_attrs
    else:
        event_class = resolve_event_topic(stored_event.event_topic)
        event_data = json.loads(stored_event.event_attrs, cls=ObjectJSONDecoder)
        try:
            domain_event = event_class(**event_data)
        except TypeError:
            raise TypeError("Unable to instantiate class '{}' with data '{}'".format(stored_event.event_topic, stored_event.event_attrs))
    return domain_event


def topic_from_domain_event(domain_event):
    """Returns a string describing a domain event class.

    Args:
        domain_event: A domain event object.

    Returns:
        A string describing the domain event object's class.
    """
    # assert isinstance(domain_event, DomainEvent)
    return domain_event.__module__ + '#' + domain_event.__class__.__qualname__


def entity_class_name_from_domain_event(domain_event):
    """Returns entity class name for the domain event.

    Args:
        domain_event: A domain event object.

    Returns:
        A string naming the domain entity class.
    """
    # assert isinstance(domain_event, DomainEvent)
    return domain_event.__class__.__qualname__.split('.')[0]


def resolve_event_topic(topic):
    """Return domain event class described by given topic.

    Args:
        topic: A string describing a domain event class.

    Returns:
        A domain event class.

    Raises:
        TopicResolutionError: If there is no such domain event class.
    """
    # Todo: Fix up this block to show what the topic is, and where it went wrong.
    try:
        module_name, _, class_name = topic.partition('#')
        module = importlib.import_module(module_name)
    except ImportError:
        raise TopicResolutionError()
    try:
        cls = resolve_attr(module, class_name)
    except AttributeError:
        raise TopicResolutionError()
    return cls


def resolve_attr(obj, path):
    """A recursive version of getattr for navigating dotted paths.

    Args:
        obj: An object for which we want to retrieve a nested attribute.
        path: A dot separated string containing zero or more attribute names.

    Returns:
        The attribute referred to by obj.a1.a2.a3...

    Raises:
        AttributeError: If there is no such attribute.
    """
    if not path:
        return obj
    head, _, tail = path.partition('.')
    head_obj = getattr(obj, head)
    return resolve_attr(head_obj, tail)


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
                # for attr, value in obj.__dict__.items():
                #     d[attr] = self.default(value)
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