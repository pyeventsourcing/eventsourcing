import importlib
import json
from eventsourcing.domain.model.events import DomainEvent
from eventsourcing.exceptions import TopicResolutionError


class StoredEvent(object):
    """Object class containing a serialized domain event.

    Attributes:
        entity_id: Identifies the entity from which the domain event arises.
        event_topic: Describes the domain event class.
        event_attrs: JSON serialization of the domain event attributes.
    """

    def __init__(self, entity_id, event_topic, event_attrs):
        self.entity_id = entity_id
        self.event_topic = event_topic
        self.event_attrs = event_attrs


def stored_event_from_domain_event(domain_event):
    """Serializes a domain event into a stored event.

    Args:
        domain_event: A domain event object.

    Returns:
        A stored event object.

    Raises:
        AssertionError: If the domain event object is not an instance of DomainEvent.
    """
    assert isinstance(domain_event, DomainEvent)
    event_topic = topic_from_domain_event(domain_event)
    event_data = json.dumps(domain_event.__dict__, separators=(',', ':'), sort_keys=True)
    return StoredEvent(domain_event.entity_id, event_topic, event_data)


def topic_from_domain_event(domain_event):
    """Returns a string describing a domain event class.

    Args:
        domain_event: A domain event object.

    Returns:
        A string describing the domain event object's class.
    """
    return domain_event.__module__ + '#' + domain_event.__class__.__qualname__


def domain_event_from_stored_event(stored_event):
    """Deserialises a stored event into the original stored event.

    Args:
        stored_event: A stored event object.

    Returns:
        A domain event object.

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
