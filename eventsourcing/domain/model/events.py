import importlib
import itertools
from abc import ABCMeta
from collections import OrderedDict
from uuid import uuid1

from six import with_metaclass

from eventsourcing.exceptions import TopicResolutionError
from eventsourcing.utils.time import timestamp_from_uuid


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


def create_domain_event_id():
    return uuid1().hex


class DomainEvent(with_metaclass(QualnameABCMeta)):

    always_encrypt = False

    def __init__(self, entity_id, entity_version, domain_event_id=None, **kwargs):
        self.__dict__['entity_id'] = entity_id
        self.__dict__['entity_version'] = entity_version
        self.__dict__['domain_event_id'] = domain_event_id or create_domain_event_id()
        self.__dict__.update(kwargs)

    def __setattr__(self, key, value):
        raise AttributeError("DomainEvent attributes are read-only")

    @property
    def entity_id(self):
        return self.__dict__['entity_id']

    @property
    def entity_version(self):
        return self.__dict__['entity_version']

    @property
    def domain_event_id(self):
        return self.__dict__['domain_event_id']

    @property
    def timestamp(self):
        return timestamp_from_uuid(self.__dict__['domain_event_id'])

    def __eq__(self, rhs):
        if type(self) is not type(rhs):
            return NotImplemented
        return self.__dict__ == rhs.__dict__

    def __ne__(self, rhs):
        return not (self == rhs)

    def __hash__(self):
        return hash(tuple(itertools.chain(sorted(self.__dict__.items()), [type(self)])))

    def __repr__(self):
        return self.__class__.__qualname__ + "(" + ', '.join(
            "{0}={1!r}".format(*item) for item in sorted(self.__dict__.items())) + ')'


_event_handlers = OrderedDict()


def subscribe(event_predicate, subscriber):
    if event_predicate not in _event_handlers:
        _event_handlers[event_predicate] = []
    _event_handlers[event_predicate].append(subscriber)


def unsubscribe(event_predicate, subscriber):
    if event_predicate in _event_handlers:
        handlers = _event_handlers[event_predicate]
        if subscriber in handlers:
            handlers.remove(subscriber)
            if not handlers:
                _event_handlers.pop(event_predicate)


def publish(event):
    matching_handlers = []
    for event_predicate, handlers in _event_handlers.items():
        if event_predicate(event):
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
        domain_event: A domain event object.

    Returns:
        A string describing the domain event object's class.
    """
    # assert isinstance(domain_event, DomainEvent)
    return domain_class.__module__ + '#' + domain_class.__qualname__


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
