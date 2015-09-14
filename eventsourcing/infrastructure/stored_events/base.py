from abc import ABCMeta, abstractmethod
from collections import namedtuple
import datetime
import importlib
import json
import uuid
from six import with_metaclass
from eventsourcing.domain.model.events import DomainEvent
from eventsourcing.exceptions import TopicResolutionError
import dateutil.parser

StoredEvent = namedtuple('StoredEvent', ['event_id', 'stored_entity_id', 'event_topic', 'event_attrs'])


class StoredEventRepository(with_metaclass(ABCMeta)):

    @abstractmethod
    def append(self, stored_event):
        """Saves given stored event in this repository.
        """

    @abstractmethod
    def __getitem__(self, event_id):
        """Returns stored event for given event ID.
        """

    @abstractmethod
    def __contains__(self, event_id):
        """Tests whether given event ID exists.
        """

    @abstractmethod
    def get_entity_events(self, stored_entity_id):
        """Returns all events for given entity ID.
        """

    @abstractmethod
    def get_topic_events(self, event_topic):
        """Returns all events for given topic.
        """


class InMemoryStoredEventRepository(StoredEventRepository):

    def __init__(self):
        self._by_id = {}
        self._by_stored_entity_id = {}
        self._by_topic = {}

    def append(self, stored_event):
        assert isinstance(stored_event, StoredEvent)
        event_id = stored_event.event_id
        stored_entity_id = stored_event.stored_entity_id
        topic = stored_event.event_topic

        # Store the event by event ID.
        self._by_id[event_id] = stored_event

        # Append the event to list for entity ID.
        if stored_entity_id not in self._by_stored_entity_id:
            self._by_stored_entity_id[stored_entity_id] = []
        self._by_stored_entity_id[stored_entity_id].append(stored_event)

        # Append the event to list for event topic.
        if topic not in self._by_topic:
            self._by_topic[topic] = []
        self._by_topic[topic].append(stored_event)

    def __getitem__(self, event_id):
        return self._by_id[event_id]

    def __contains__(self, event_id):
        return event_id in self._by_id

    def get_entity_events(self, stored_entity_id):
        if stored_entity_id not in self._by_stored_entity_id:
            return []
        else:
            return self._by_stored_entity_id[stored_entity_id]

    def get_topic_events(self, event_topic):
        return self._by_topic[event_topic]


def serialize_domain_event(domain_event):
    """Serializes a domain event into a stored event.

    Args:
        domain_event: A domain event object.

    Returns:
        A stored event object.

    Raises:
        AssertionError: If the domain event object is not an instance of DomainEvent.
    """
    assert isinstance(domain_event, DomainEvent)
    event_id = uuid.uuid1().hex
    stored_entity_id = entity_type_name_from_domain_event(domain_event) + '::' + domain_event.entity_id
    event_topic = topic_from_domain_event(domain_event)
    event_attrs = json.dumps(domain_event.__dict__, separators=(',', ':'), sort_keys=True, cls=ObjectJSONEncoder)
    return StoredEvent(
        event_id=event_id,
        stored_entity_id=stored_entity_id,
        event_topic=event_topic,
        event_attrs=event_attrs,
    )


def recreate_domain_event(stored_event):
    """Recreates original domain event from stored event topic and event attrs.

    Args:
        stored_event: A stored domain event object (instance of StoredEvent).

    Returns:
        A domain event object (instance of DomainEvent).

    Raises:
        AssertionError: If the stored event is not an instance of StoredEvent.
        TopicResolutionError: If the stored event topic could not be resolved.
        ValueError: If the stored event data could not be parsed as JSON.
    """
    assert isinstance(stored_event, StoredEvent)
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
    assert isinstance(domain_event, DomainEvent)
    return domain_event.__module__ + '#' + domain_event.__class__.__qualname__


def entity_type_name_from_domain_event(domain_event):
    """Returns entity class name for the domain event.

    Args:
        domain_event: A domain event object.

    Returns:
        A string naming the domain entity class.
    """
    assert isinstance(domain_event, DomainEvent)
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
            else:
                d = { '__class__': obj.__class__.__qualname__,
                      '__module__': obj.__module__,
                    }
                d.update(obj.__dict__)
                return d


class ObjectJSONDecoder(json.JSONDecoder):

    def __init__(self, **kwargs):
        super(ObjectJSONDecoder, self).__init__(object_hook=ObjectJSONDecoder.from_jsonable, **kwargs)

    @staticmethod
    def from_jsonable(d):
        if '__class__' in d and '__module__' in d:
            return ObjectJSONDecoder._decode_class(d)
        elif 'ISO8601_datetime' in d:
            return ObjectJSONDecoder._decode_datetime(d)
        elif 'ISO8601_date' in d:
            return ObjectJSONDecoder._decode_date(d)
        return d

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
            obj.__dict__.update(d)
        return obj

    @staticmethod
    def _decode_date(d):
        return datetime.datetime.strptime(d['ISO8601_date'], '%Y-%m-%d').date()

    @staticmethod
    def _decode_datetime(d):
        return dateutil.parser.parse(d['ISO8601_datetime'])
