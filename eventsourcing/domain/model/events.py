import os
import time
from abc import ABCMeta
from collections import OrderedDict
from uuid import uuid1

import six
from six import with_metaclass

from eventsourcing.exceptions import EventHashError
from eventsourcing.utils.hashing import hash_for_data_integrity
from eventsourcing.utils.times import decimaltimestamp
from eventsourcing.utils.topic import get_topic
from eventsourcing.utils.transcoding import ObjectJSONEncoder

GENESIS_HASH = os.getenv('GENESIS_HASH', '')


class QualnameABCMeta(ABCMeta):
    """
    Supplies __qualname__ to object classes with this metaclass.
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
    __with_data_integrity__ = False
    __json_encoder_class__ = ObjectJSONEncoder

    def __init__(self, **kwargs):
        """
        Initialises event attribute values directly from constructor kwargs.
        """
        if self.__with_data_integrity__:
            kwargs['__event_topic__'] = get_topic(type(self))
            # Seal the event with a hash of the other values.
            assert '__event_hash__' not in kwargs
            event_hash = self.__hash_for_data_integrity__(kwargs)
            kwargs['__event_hash__'] = event_hash

        self.__dict__.update(kwargs)

    @classmethod
    def __hash_for_data_integrity__(cls, obj):
        return hash_for_data_integrity(cls.__json_encoder_class__, obj)

    @property
    def __event_hash__(self):
        return self.__dict__.get('__event_hash__')

    def __check_hash__(self):
        state = self.__dict__.copy()
        event_hash = state.pop('__event_hash__')
        if event_hash != self.__hash_for_data_integrity__(state):
            raise EventHashError()

    def __mutate__(self, obj):
        """
        Update obj with values from self.

        Can be extended, but subclasses must call super
        method, and return an object.

        :param obj: object to be mutated
        :return: mutated object
        """
        # Check the event and the object.
        if self.__with_data_integrity__:
            # Todo: Refactor: "replace assert with test" (ie, an if statement).
            assert self.__dict__['__event_topic__'] == get_topic(type(self))
            self.__check_hash__()

        # Call mutate() method.
        self.mutate(obj)

        return obj

    def mutate(self, obj):
        """
        Convenience for use in custom models, to update
        obj with values from self without needing to call
        super method and return obj (two extra lines).

        Can be overridden by subclasses. Any value returned
        by this method will be ignored.

        Please note, subclasses that extend mutate() might
        not have fully completed that method before this method
        is called. To ensure all base classes have completed
        their mutate behaviour before mutating an event in a concrete
        class, extend mutate() instead of overriding this method.

        :param obj: object to be mutated
        """

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
        Computes a Python integer hash for an event,
        using its event hash string if available.

        Supports equality and inequality comparisons.
        """
        return hash((
            self.__event_hash__ or self.__hash_for_data_integrity__(
                self.__dict__
            ), self.__class__
        ))

    def __repr__(self):
        """
        Returns string representing the type and attribute values of the event.
        """
        sorted_items = tuple(sorted(self.__dict__.items()))
        args_strings = ("{0}={1!r}".format(*item) for item in sorted_items)
        args_string = ', '.join(args_strings)
        return "{}({})".format(self.__class__.__qualname__, args_string)


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
        kwargs['timestamp'] = timestamp or decimaltimestamp()
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
