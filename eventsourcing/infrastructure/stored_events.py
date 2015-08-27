from abc import ABCMeta, abstractmethod
from collections import namedtuple
import importlib
import json
import uuid

from eventsourcing.domain.model.events import DomainEvent
from eventsourcing.exceptions import TopicResolutionError

StoredEvent = namedtuple('StoredEvent', ['event_id', 'entity_id', 'event_topic', 'event_attrs'])


class StoredEventRepository(metaclass=ABCMeta):

    @abstractmethod
    def append(self, stored_event):
        raise NotImplementedError

    @abstractmethod
    def __getitem__(self, item):
        raise NotImplementedError

    @abstractmethod
    def __contains__(self, item):
        raise NotImplementedError

    @abstractmethod
    def get_entity_events(self, entity_id):
        raise NotImplementedError

    @abstractmethod
    def get_topic_events(self, event_topic):
        raise NotImplementedError


class InMemoryStoredEventRepository(StoredEventRepository):

    def __init__(self):
        self._by_id = {}
        self._by_entity_id = {}
        self._by_topic = {}

    def append(self, stored_event):
        assert isinstance(stored_event, StoredEvent)
        event_id = stored_event.event_id
        entity_id = stored_event.entity_id
        topic = stored_event.event_topic

        # Store the event by event ID.
        self._by_id[event_id] = stored_event

        # Append the event to list for entity ID.
        if entity_id not in self._by_entity_id:
            self._by_entity_id[entity_id] = []
        self._by_entity_id[entity_id].append(stored_event)

        # Append the event to list for event topic.
        if topic not in self._by_topic:
            self._by_topic[topic] = []
        self._by_topic[topic].append(stored_event)

    def __getitem__(self, item):
        return self._by_id[item]

    def __contains__(self, item):
        return item in self._by_id

    def get_entity_events(self, entity_id):
        if entity_id not in self._by_entity_id:
            return []
        else:
            return self._by_entity_id[entity_id]

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
    event_id = uuid.uuid4()
    entity_id = domain_event.entity_id
    event_topic = topic_from_domain_event(domain_event)
    event_attrs = json.dumps(domain_event.__dict__, separators=(',', ':'), sort_keys=True)
    return StoredEvent(
        event_id=event_id,
        entity_id=entity_id,
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
    event_data = json.loads(stored_event.event_attrs)
    domain_event = event_class(**event_data)
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


def resolve_event_topic(topic):
    """Return domain event class described by given topic.

    Args:
        topic: A string describing a domain event class.

    Returns:
        A domain event class.

    Raises:
        TopicResolutionError: If there is no such domain event class.
    """
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
