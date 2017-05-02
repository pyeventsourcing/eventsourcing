import importlib
import itertools
import time
from abc import ABCMeta
from collections import OrderedDict
from uuid import uuid1

import six
from six import with_metaclass

from eventsourcing.exceptions import TopicResolutionError



class QualnameABCMeta(ABCMeta):
    """Supplies __qualname__ to object classes with this metaclass.
    """
    __outer_classes = {}

    if not hasattr(object, '__qualname__'):

        def __init__(cls, name, bases, dict):
            super(QualnameABCMeta, cls).__init__(name, bases, dict)
            QualnameABCMeta.__outer_classes[cls] = None
            for class_attr in dict.values():  # iterate class attributes
                for outer_class in QualnameABCMeta.__outer_classes:
                    if class_attr == outer_class:  # is the object an already registered type?
                        QualnameABCMeta.__outer_classes[outer_class] = cls
                        break

        @property
        def __qualname__(cls):
            c = QualnameABCMeta.__outer_classes[cls]
            if c is None:
                return cls.__name__
            else:
                return "%s.%s" % (c.__qualname__, cls.__name__)


def create_timesequenced_event_id():
    return uuid1().hex


class QualnameABC(with_metaclass(QualnameABCMeta)):
    """
    Base class that introduces __qualname__ for objects in Python 2.7.
    """


class DomainEvent(QualnameABC):
    """
    Base class for domain events.

    Implements methods to make instances read-only, comparable
    for equality, have recognisable representations, and hashable.
    """
    __always_encrypt__ = False

    def __init__(self, **kwargs):
        """
        Initialises event attribute values directly from constructor kwargs.
        """
        self.__dict__.update(kwargs)

    def __setattr__(self, key, value):
        """
        Inhibits event attributes from being updated by assignment.
        """
        raise AttributeError("DomainEvent attributes are read-only")

    def __eq__(self, other):
        """
        Tests for equality of type and attribute values.
        """
        return type(self) == type(other) and self.__dict__ == other.__dict__

    def __ne__(self, other):
        """
        Negates the equality test.
        """
        return not (self == other)

    def __hash__(self):
        """
        Computes a unique hash for an event, using its type and attribute values.
        """
        return hash(tuple(itertools.chain(sorted(self.__dict__.items()), [type(self)])))

    def __repr__(self):
        """
        Returns string representing the type and attribute values of the event.
        """
        return self.__class__.__qualname__ + "(" + ', '.join(
            "{0}={1!r}".format(*item) for item in sorted(self.__dict__.items())) + ')'


class EventWithOriginatorID(DomainEvent):
    def __init__(self, originator_id, **kwargs):
        super(EventWithOriginatorID, self).__init__(**kwargs)
        self.__dict__['originator_id'] = originator_id

    @property
    def originator_id(self):
        return self.__dict__['originator_id']


class EventWithTimestamp(DomainEvent):
    """
    For events that have a timestamp value.
    """

    def __init__(self, timestamp=None, **kwargs):
        super(EventWithTimestamp, self).__init__(**kwargs)
        self.__dict__['timestamp'] = timestamp or time.time()

    @property
    def timestamp(self):
        return self.__dict__['timestamp']


class EventWithOriginatorVersion(DomainEvent):
    """
    For events that have an originator version number.
    """

    def __init__(self, originator_version, **kwargs):
        if not isinstance(originator_version, six.integer_types):
            raise TypeError("Version must be an integer: {}".format(originator_version))
        super(EventWithOriginatorVersion, self).__init__(**kwargs)
        self.__dict__['originator_version'] = originator_version

    @property
    def originator_version(self):
        return self.__dict__['originator_version']


class EventWithTimeuuid(DomainEvent):
    """
    For events that have an UUIDv1 event ID.
    """

    def __init__(self, event_id=None, **kwargs):
        super(EventWithTimeuuid, self).__init__(**kwargs)
        self.__dict__['event_id'] = event_id or uuid1()

    @property
    def event_id(self):
        return self.__dict__['event_id']


class Created(DomainEvent):
    """
    Can be published when an entity is created.
    """


class AttributeChanged(DomainEvent):
    """
    Can be published when an attribute of an entity is created.
    """
    @property
    def name(self):
        return self.__dict__['name']

    @property
    def value(self):
        return self.__dict__['value']


class Discarded(DomainEvent):
    """
    Published when something is discarded.
    """


class Logged(DomainEvent):
    """
    Published when something is logged.
    """


_event_handlers = OrderedDict()


def subscribe(handler, predicate=None):
    if predicate not in _event_handlers:
        _event_handlers[predicate] = []
    _event_handlers[predicate].append(handler)


def unsubscribe(handler, predicate=None):
    if predicate in _event_handlers:
        handlers = _event_handlers[predicate]
        if handler in handlers:
            handlers.remove(handler)
            if not handlers:
                _event_handlers.pop(predicate)


def publish(event):
    matching_handlers = []
    for predicate, handlers in _event_handlers.items():
        if predicate is None or predicate(event):
            for handler in handlers:
                if handler not in matching_handlers:
                    matching_handlers.append(handler)
    for handler in matching_handlers:
        handler(event)


class EventHandlersNotEmptyError(Exception):
    pass


def assert_event_handlers_empty():
    if len(_event_handlers):
        msg = "Event handlers are still subscribed: %s" % _event_handlers
        raise EventHandlersNotEmptyError(msg)


def topic_from_domain_class(domain_class):
    """Returns a string describing a domain event class.

    Args:
        domain_class: A domain entity or event class.

    Returns:
        A string describing the class.
    """
    return domain_class.__module__ + '#' + getattr(domain_class, '__qualname__', domain_class.__name__)


def resolve_domain_topic(topic):
    """Return domain class described by given topic.

    Args:
        topic: A string describing a domain class.

    Returns:
        A domain class.

    Raises:
        TopicResolutionError: If there is no such domain class.
    """
    try:
        module_name, _, class_name = topic.partition('#')
        module = importlib.import_module(module_name)
    except ImportError as e:
        raise TopicResolutionError("{}: {}".format(topic, e))
    try:
        cls = resolve_attr(module, class_name)
    except AttributeError as e:
        raise TopicResolutionError("{}: {}".format(topic, e))
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


def reconstruct_object(obj_class, obj_state):
    obj = object.__new__(obj_class)
    obj.__dict__.update(obj_state)
    return obj
