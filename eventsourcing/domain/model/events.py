import hashlib
import itertools
import json
import time
from abc import ABCMeta
from collections import OrderedDict
from uuid import uuid1

import os
import six
from six import with_metaclass

from eventsourcing.exceptions import EventHashError
from eventsourcing.utils.topic import resolve_topic
from eventsourcing.utils.transcoding import ObjectJSONEncoder

GENESIS_HASH = os.getenv('GENESIS_HASH', '')


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
    return uuid1()


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
    __json_encoder_class__ = ObjectJSONEncoder
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
        Tests for equality of two event objects.
        """
        return self.__hash__() == other.__hash__()

    def __ne__(self, other):
        """
        Negates the equality test.
        """
        return not (self == other)

    def __hash__(self):
        """
        Computes a Python integer hash for an event, using its type and attribute values.
        """
        return hash(self.hash(self.__dict__))

    def __repr__(self):
        """
        Returns string representing the type and attribute values of the event.
        """
        sorted_items = tuple(sorted(self.__dict__.items()))
        return self.__class__.__qualname__ + "(" + ', '.join(
            "{0}={1!r}".format(*item) for item in sorted_items) + ')'

    @classmethod
    def hash(cls, *args):
        json_dump = json.dumps(
            args,
            separators=(',', ':'),
            sort_keys=True,
            cls=cls.__json_encoder_class__,
        )
        return hashlib.sha256(json_dump.encode()).hexdigest()


class EventWithOriginatorID(DomainEvent):
    def __init__(self, originator_id, **kwargs):
        kwargs['originator_id'] = originator_id
        super(EventWithOriginatorID, self).__init__(**kwargs)

    @property
    def originator_id(self):
        return self.__dict__['originator_id']


class EventWithTimestamp(DomainEvent):
    """
    For events that have a timestamp value.
    """

    def __init__(self, timestamp=None, **kwargs):
        kwargs['timestamp'] = timestamp or time.time()
        super(EventWithTimestamp, self).__init__(**kwargs)

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
        kwargs['originator_version'] = originator_version
        super(EventWithOriginatorVersion, self).__init__(**kwargs)

    @property
    def originator_version(self):
        return self.__dict__['originator_version']


class EventWithTimeuuid(DomainEvent):
    """
    For events that have an UUIDv1 event ID.
    """

    def __init__(self, event_id=None, **kwargs):
        kwargs['event_id'] = event_id or uuid1()
        super(EventWithTimeuuid, self).__init__(**kwargs)

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
