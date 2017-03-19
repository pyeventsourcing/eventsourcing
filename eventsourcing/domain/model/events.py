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


class DomainEvent(with_metaclass(QualnameABCMeta)):
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
        raise AttributeError("OldDomainEvent attributes are read-only")

    def __eq__(self, rhs):
        """
        Tests for equality of type and attribute values.
        """
        if type(self) is not type(rhs):
            return NotImplemented
        return self.__dict__ == rhs.__dict__

    def __ne__(self, rhs):
        """
        Negates the equality test.
        """
        return not (self == rhs)

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


class EntityEvent(DomainEvent):
    """
    For events that have an entity ID attribute.
    """

    def __init__(self, entity_id, **kwargs):
        super(EntityEvent, self).__init__(**kwargs)
        self.__dict__['entity_id'] = entity_id

    @property
    def entity_id(self):
        return self.__dict__['entity_id']


class EventWithTimestamp(DomainEvent):
    """
    For events that have an timestamp attribute.
    """

    def __init__(self, timestamp=None, **kwargs):
        super(EventWithTimestamp, self).__init__(**kwargs)
        self.__dict__['timestamp'] = timestamp or time.time()

    @property
    def timestamp(self):
        return self.__dict__['timestamp']


class EventWithEntityVersion(DomainEvent):
    """
    For events that have an entity version number.
    """

    def __init__(self, entity_version, **kwargs):
        if not isinstance(entity_version, six.integer_types):
            raise TypeError("Version must be an integer: {}".format(entity_version))
        super(EventWithEntityVersion, self).__init__(**kwargs)
        self.__dict__['entity_version'] = entity_version

    @property
    def entity_version(self):
        return self.__dict__['entity_version']


class TimestampedEntityEvent(EventWithTimestamp, EntityEvent):
    """
    For events of timestamp-based entities (e.g. a log).
    """


class VersionedEntityEvent(EventWithEntityVersion, EntityEvent):
    """
    For events of versioned entities.
    """


class TimestampedVersionedEntityEvent(EventWithTimestamp, VersionedEntityEvent):
    """
    For events of version-based entities, that are also timestamped.
    """

class AggregateEvent(TimestampedVersionedEntityEvent):
    """
    For events of DDD aggregates.
    """


# class OldDomainEvent(DomainEvent):
#     """
#     Original domain event.
#
#     Due to the origins of the project, this design ended
#     up as a confusion of time-sequenced and integer-sequenced
#     events. It was used for both time-sequenced streams, such
#     as time-bucketed logs and snapshots, where the entity
#     version number appeared as the code smell known as "refused
#     bequest". It was also used for integer sequenced streams,
#     such as versioned domain entities, where the timestamp-based
#     implementation threatened inconsistency due to network issues.
#     The "solution" to the timestamp-based integer sequencing was
#     to have a second table controlling consistency of integer
#     sequenced. But working across two tables without cross-table
#     transaction support (e.g. in Cassandra) is a dead-end. Now,
#     integer sequenced domain events don't essentially require
#     to know what time they happened.
#
#     Therefore it must be much better to have two separate types
#     of domain event: time-sequenced events, and integer-sequenced
#     events. Domain entities and notification logs can have integer-
#     sequenced events, and snapshots and time-bucketed logs can
#     have time-sequenced events.
#
#     That's why this class has been deprecated :-).
#     """
#
#     def __init__(self, entity_id, entity_version, domain_event_id=None, **kwargs):
#         super(OldDomainEvent, self).__init__(**kwargs)
#         self.__dict__['entity_id'] = entity_id
#         self.__dict__['entity_version'] = entity_version
#         self.__dict__['domain_event_id'] = domain_event_id or create_timesequenced_event_id()
#
#     @property
#     def entity_id(self):
#         return self.__dict__['entity_id']
#
#     @property
#     def entity_version(self):
#         return self.__dict__['entity_version']
#
#     @property
#     def domain_event_id(self):
#         return self.__dict__['domain_event_id']
#
#     @property
#     def timestamp(self):
#         return timestamp_from_uuid(self.__dict__['domain_event_id'])


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
        domain_class: A domain entity or event class.

    Returns:
        A string describing the class.
    """
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
