import os
from collections import OrderedDict
from uuid import uuid1

from eventsourcing.exceptions import EventHashError
from eventsourcing.utils.hashing import hash_object
from eventsourcing.utils.times import decimaltimestamp
from eventsourcing.utils.topic import get_topic
from eventsourcing.utils.transcoding import ObjectJSONEncoder

GENESIS_HASH = os.getenv('GENESIS_HASH', '')


def create_timesequenced_event_id():
    return uuid1()


class DomainEvent(object):
    """
    Base class for domain events.

    Implements methods to make instances read-only,
    comparable for equality in Python, and have
    recognisable representations.

    To make domain events hashable, this class also
    implements a method to create a cryptographic hash
    of the state of the event.
    """
    __json_encoder_class__ = ObjectJSONEncoder
    __notifiable__ = True

    def __init__(self, **kwargs):
        """
        Initialises event attribute values directly from constructor kwargs.
        """
        self.__dict__.update(kwargs)

    def __repr__(self):
        """
        Creates a string representing the type and attribute values of the event.

        :rtype: str
        """
        sorted_items = tuple(sorted(self.__dict__.items()))
        args_strings = ("{0}={1!r}".format(*item) for item in sorted_items)
        args_string = ', '.join(args_strings)
        return "{}({})".format(self.__class__.__qualname__, args_string)

    def __mutate__(self, obj):
        """
        Updates 'obj' with values from 'self'.

        Calls the 'mutate()' method.

        Can be extended, but subclasses must call super
        and return an object to their caller.

        :param obj: object (normally a domain entity) to be mutated
        :return: mutated object
        """
        self.mutate(obj)
        return obj

    def mutate(self, obj):
        """
        Updates ("mutates") given 'obj'.

        Intended to be overridden by subclasses, as the most
        concise way of coding a default projection of the event
        (for example into the state of a domain entity).

        The advantage of implementing a default projection
        using this method rather than __mutate__ is that you
        don't need to call super or return a value.

        :param obj: domain entity to be mutated
        """

    def __setattr__(self, key, value):
        """
        Inhibits event attributes from being updated by assignment.
        """
        raise AttributeError("DomainEvent attributes are read-only")

    def __eq__(self, other):
        """
        Tests for equality of two event objects.

        :rtype: bool
        """
        return isinstance(other, DomainEvent) and self.__hash__() == other.__hash__()

    def __ne__(self, other):
        """
        Negates the equality test.

        :rtype: bool
        """
        return not (self == other)

    def __hash__(self):
        """
        Computes a Python integer hash for an event.

        Supports Python equality and inequality comparisons.

        :return: Python integer hash
        :rtype: int
        """
        state = self.__dict__.copy()
        state['__event_topic__'] = get_topic(type(self))

        # Calculate the cryptographic hash of the event.
        sha256_hash = self.__hash_object__(state)

        # Return the Python hash of the cryptographic hash.
        return hash(sha256_hash)

    @classmethod
    def __hash_object__(cls, obj):
        """
        Calculates SHA-256 hash of JSON encoded 'obj'.

        :param obj: Object to be hashed.
        :return: SHA-256 as hexadecimal string.
        :rtype: str
        """
        return hash_object(cls.__json_encoder_class__, obj)


class EventWithHash(DomainEvent):
    """
    Base class for domain events with a cryptographic event hash.

    Extends DomainEvent by setting a cryptographic event hash
    when the event is originated, and checking the event hash
    whenever its default projection mutates an object.
    """

    def __init__(self, **kwargs):
        super(EventWithHash, self).__init__(**kwargs)

        # Set __event_topic__ to differentiate events of
        # different types with otherwise equal attributes.
        self.__dict__['__event_topic__'] = get_topic(type(self))

        # Set __event_hash__ with a SHA-256 hash of the event.
        self.__dict__['__event_hash__'] = self.__hash_object__(self.__dict__)

    @property
    def __event_hash__(self):
        """
        Returns SHA-256 hash of the original state of the event.

        :return: SHA-256 as hexadecimal string.
        :rtype: str
        """
        return self.__dict__.get('__event_hash__')

    def __hash__(self):
        """
        Computes a Python integer hash for an event,
        using its pre-computed event hash.

        Supports Python equality and inequality comparisons only.

        :return: Python integer hash
        :rtype: int
        """
        # Return the Python hash of the cryptographic hash.
        return hash(self.__event_hash__)

    def __mutate__(self, obj):
        """
        Updates 'obj' with values from self.

        Can be extended, but subclasses must call super
        method, and return an object.

        :param obj: object to be mutated
        :return: mutated object
        """

        # Check the hash.
        self.__check_hash__()

        # Call super and return value.
        return super(EventWithHash, self).__mutate__(obj)

    def __check_hash__(self):
        """
        Raises EventHashError, unless self.__event_hash__ can
        be derived from the current state of the event object.
        """
        state = self.__dict__.copy()
        event_hash = state.pop('__event_hash__')
        if event_hash != self.__hash_object__(state):
            raise EventHashError()


class EventWithOriginatorID(DomainEvent):
    """
    For events that have an originator ID.
    """
    def __init__(self, originator_id, **kwargs):
        kwargs['originator_id'] = originator_id
        super(EventWithOriginatorID, self).__init__(**kwargs)

    @property
    def originator_id(self):
        """
        Originator ID is the identity of the object
        that originated this event.

        :return: A UUID representing the identity of the originator.
        :rtype: UUID
        """
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
        """
        A UNIX timestamp as a Decimal object.

        :rtype: Decimal
        """
        return self.__dict__['timestamp']


class EventWithOriginatorVersion(DomainEvent):
    """
    For events that have an originator version number.
    """

    def __init__(self, originator_version, **kwargs):
        if not isinstance(originator_version, int):
            raise TypeError("Version must be an integer: {}".format(originator_version))
        kwargs['originator_version'] = originator_version
        super(EventWithOriginatorVersion, self).__init__(**kwargs)

    @property
    def originator_version(self):
        """
        Originator version is the version of the object
        that originated this event.

        :return: A integer representing the version of the originator.
        :rtype: int
        """
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
    Can be originated when something is created.
    """


class AttributeChanged(DomainEvent):
    """
    Can be originated when the value of an attribute changes.
    """

    @property
    def name(self):
        return self.__dict__['name']

    @property
    def value(self):
        return self.__dict__['value']


class Discarded(DomainEvent):
    """
    Can be originated when something is discarded.
    """


class Logged(DomainEvent):
    """
    Can be originated when something is logged.
    """


_subscriptions = []


def subscribe(handler, predicate=None):
    """
    Adds 'handler' to list of event handlers
    to be called if 'predicate' is satisfied.

    If predicate is None, the handler will
    be called whenever an event is published.

    :param handler: Will be called when an event is published.
    :param predicate: Conditions whether the handler will be called.
    """
    if (predicate, handler) not in _subscriptions:
        _subscriptions.append((predicate, handler))


def unsubscribe(handler, predicate=None):
    """
    Removes 'handler' from list of event handlers
    to be called if 'predicate' is satisfied.

    :param handler:
    :param predicate:
    """
    if (predicate, handler) in _subscriptions:
        _subscriptions.remove((predicate, handler))


def publish(event):
    """
    Calls subscribed event handlers with the
    given 'event', except those with predicates
    that are not satisfied by the event.

    :param event:
    """
    for predicate, handler in _subscriptions[:]:
        if predicate is None or predicate(event):
            handler(event)


class EventHandlersNotEmptyError(Exception):
    pass


def assert_event_handlers_empty():
    """
    Raises EventHandlersNotEmptyError, unless
    there are no event handlers subscribed.
    """
    if len(_subscriptions):
        msg = "subscriptions still exist: %s" % _subscriptions
        raise EventHandlersNotEmptyError(msg)


def clear_event_handlers():
    """
    Removes all previously subscribed event handlers.
    """
    _subscriptions.clear()
