from abc import abstractmethod
from decimal import Decimal
from typing import Any, Callable, Dict, Generic, List, Optional, Sequence, Tuple
from uuid import UUID, uuid1

from eventsourcing.domain.model.versioning import Upcastable
from eventsourcing.exceptions import EventHashError
from eventsourcing.utils import transcoding_v1
from eventsourcing.utils.hashing import hash_object
from eventsourcing.utils.times import decimaltimestamp
from eventsourcing.utils.topic import get_topic
from eventsourcing.utils.transcoding import ObjectJSONEncoder
from eventsourcing.whitehead import ActualOccasion, TEntity, TEvent


class DomainEvent(Upcastable, ActualOccasion, Generic[TEntity]):
    """
    Base class for domain model events.

    Implements methods to make instances read-only,
    comparable for equality in Python, and have
    recognisable representations.Custom
    To make domain events hashable, this class also
    implements a method to create a cryptographic hash
    of the state of the event.
    """

    __json_encoder_v2__ = ObjectJSONEncoder(sort_keys=True)
    __json_encoder_v1__ = transcoding_v1.ObjectJSONEncoder(sort_keys=True)
    __notifiable__ = True

    def __init__(self, **kwargs: Any):
        """
        Initialises event attribute values directly from constructor kwargs.
        """
        super().__init__()
        self.__dict__.update(kwargs)

    def __repr__(self) -> str:
        """
        Creates a string representing the type and attribute values of the event.

        :rtype: str
        """
        sorted_items = tuple(sorted(self.__dict__.items()))
        args_strings = ("{0}={1!r}".format(*item) for item in sorted_items)
        args_string = ", ".join(args_strings)
        return "{}({})".format(self.__class__.__qualname__, args_string)

    def __mutate__(self, obj: Optional[TEntity]) -> Optional[TEntity]:
        """
        Updates 'obj' with values from 'self'.

        Calls the 'mutate()' method.

        Can be extended, but subclasses must call super
        and return an object to their caller.

        :param obj: object (normally a domain entity) to be mutated
        :return: mutated object
        """
        if obj is not None:
            self.mutate(obj)
        return obj

    def mutate(self, obj: TEntity) -> None:
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

    def __setattr__(self, key: Any, value: Any) -> None:
        """
        Inhibits event attributes from being updated by assignment.
        """
        raise AttributeError("DomainEvent attributes are read-only")

    def __eq__(self, other: object) -> bool:
        """
        Tests for equality of two event objects.

        :rtype: bool
        """
        return isinstance(other, DomainEvent) and self.__hash__() == other.__hash__()

    # Todo: Do we need this in Python 3?
    def __ne__(self, other: object) -> bool:
        """
        Negates the equality test.

        :rtype: bool
        """
        return not (self == other)

    def __hash__(self) -> int:
        """
        Computes a Python integer hash for an event.

        Supports Python equality and inequality comparisons.

        :return: Python integer hash
        :rtype: int
        """
        attrs = self.__dict__.copy()

        # Involve the topic in the hash, so that different types
        # with same attribute values have different hash values.
        attrs["__event_topic__"] = get_topic(type(self))

        # Calculate the cryptographic hash of the event.
        sha256_hash = self.__hash_object_v2__(attrs)

        # Return the Python hash of the cryptographic hash.
        return hash(sha256_hash)

    @classmethod
    def __hash_object_v2__(cls, obj: dict) -> str:
        """
        Calculates SHA-256 hash of JSON encoded 'obj'.

        :param obj: Object to be hashed.
        :return: SHA-256 as hexadecimal string.
        :rtype: str
        """
        return hash_object(cls.__json_encoder_v2__, obj)

    @classmethod
    def __hash_object_v1__(cls, obj: dict) -> str:
        """
        Calculates SHA-256 hash of JSON encoded 'obj'.

        :param obj: Object to be hashed.
        :return: SHA-256 as hexadecimal string.
        :rtype: str
        """
        return hash_object(cls.__json_encoder_v1__, obj)


class EventWithHash(DomainEvent[TEntity]):
    """
    Base class for domain events with a cryptographic event hash.

    Extends DomainEvent by setting a cryptographic event hash
    when the event is originated, and checking the event hash
    whenever its default projection mutates an object.
    """

    def __init__(self, **kwargs: Any):
        super(EventWithHash, self).__init__(**kwargs)

        # Set __event_topic__ to differentiate events of
        # different types with otherwise equal attributes.
        self.__dict__["__event_topic__"] = get_topic(type(self))

        # Set __event_hash__ with a SHA-256 hash of the event.
        hash_method = self.__hash_object_v2__
        self.__dict__["__event_hash_method_name__"] = hash_method.__name__
        self.__dict__["__event_hash__"] = hash_method(self.__dict__)

    @property
    def __event_hash__(self) -> Any:
        """
        Returns SHA-256 hash of the original state of the event.

        :return: SHA-256 as hexadecimal string.
        :rtype: str
        """
        return self.__dict__.get("__event_hash__")

    def __hash__(self) -> int:
        """
        Computes a Python integer hash for an event,
        using its pre-computed event hash.

        Supports Python equality and inequality comparisons only.

        :return: Python integer hash
        :rtype: int
        """
        # Return the Python hash of the cryptographic hash.
        return hash(self.__event_hash__)

    def __mutate__(self, obj: Optional[TEntity]) -> Optional[TEntity]:
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
        return super().__mutate__(obj)

    def __check_hash__(self) -> None:
        """
        Raises EventHashError, unless self.__event_hash__ can
        be derived from the current state of the event object.
        """
        state = self.__dict__.copy()
        event_hash = state.pop("__event_hash__")
        method_name = state.get("__event_hash_method_name__", "__hash_object_v1__")
        hash_method = getattr(self, method_name)
        if event_hash != hash_method(state):
            raise EventHashError()


class EventWithOriginatorID(DomainEvent[TEntity]):
    """
    For events that have an originator ID.
    """

    def __init__(self, originator_id: UUID, **kwargs: Any):
        super(EventWithOriginatorID, self).__init__(
            originator_id=originator_id, **kwargs
        )

    @property
    def originator_id(self) -> UUID:
        """
        Originator ID is the identity of the object
        that originated this event.

        :return: A UUID representing the identity of the originator.
        :rtype: UUID
        """
        return self.__dict__["originator_id"]


class EventWithTimestamp(DomainEvent[TEntity]):
    """
    For events that have a timestamp value.
    """

    def __init__(self, timestamp: Optional[Decimal] = None, **kwargs: Any):
        kwargs["timestamp"] = timestamp or decimaltimestamp()
        super(EventWithTimestamp, self).__init__(**kwargs)

    @property
    def timestamp(self) -> Decimal:
        """
        A UNIX timestamp as a Decimal object.
        """
        return self.__dict__["timestamp"]


class EventWithOriginatorVersion(DomainEvent[TEntity]):
    """
    For events that have an originator version number.
    """

    def __init__(self, originator_version: int, **kwargs: Any):
        if not isinstance(originator_version, int):
            raise TypeError("Version must be an integer: {}".format(originator_version))
        super(EventWithOriginatorVersion, self).__init__(
            originator_version=originator_version, **kwargs
        )

    @property
    def originator_version(self) -> int:
        """
        Originator version is the version of the object
        that originated this event.

        :return: A integer representing the version of the originator.
        """
        return self.__dict__["originator_version"]


class EventWithTimeuuid(DomainEvent[TEntity]):
    """
    For events that have an UUIDv1 event ID.
    """

    def __init__(self, event_id: Optional[UUID] = None, **kwargs: Any):
        kwargs["event_id"] = event_id or uuid1()
        super(EventWithTimeuuid, self).__init__(**kwargs)

    @property
    def event_id(self) -> UUID:
        return self.__dict__["event_id"]


class CreatedEvent(DomainEvent[TEntity]):
    """
    Happens when something is created.
    """


class AttributeChangedEvent(DomainEvent[TEntity]):
    """
    Happens when the value of an attribute changes.
    """

    @property
    def name(self) -> str:
        return self.__dict__["name"]

    @property
    def value(self) -> Any:
        return self.__dict__["value"]


class DiscardedEvent(DomainEvent[TEntity]):
    """
    Happens when something is discarded.
    """


class LoggedEvent(DomainEvent[TEntity]):
    """
    Happens when something is logged.
    """


Predicate = Callable[[Sequence[TEvent]], bool]
Handler = Callable[[Sequence[TEvent]], None]

_subscriptions: List[Tuple[Optional[Predicate], Handler]] = []


def subscribe(handler: Handler, predicate: Optional[Predicate] = None) -> None:
    """
    Adds 'handler' to list of event handlers
    to be called if 'predicate' is satisfied.

    If predicate is None, the handler will
    be called whenever an event is published.

    :param callable handler: Will be called when an event is published.
    :param callable predicate: Conditions whether the handler will be called.
    """
    if (predicate, handler) not in _subscriptions:
        _subscriptions.append((predicate, handler))


def unsubscribe(handler: Handler, predicate: Optional[Predicate] = None) -> None:
    """
    Removes 'handler' from list of event handlers
    to be called if 'predicate' is satisfied.

    :param callable handler: Previously subscribed handler.
    :param callable predicate: Previously subscribed predicate.
    """
    if (predicate, handler) in _subscriptions:
        _subscriptions.remove((predicate, handler))


def publish(events: Sequence[TEvent]) -> None:
    """
    Published given 'event' by calling subscribed event
    handlers with the given 'event', except those with
    predicates that are not satisfied by the event.

    Handlers are called in the order they are subscribed.

    :param DomainEvent events: Domain event to be published.
    """
    # A cache of conditions means predicates aren't evaluated
    # more than once for each event.
    cache: Dict[Predicate, bool] = {}
    for predicate, handler in _subscriptions[:]:
        if predicate is None:
            handler(events)
        else:
            cached_condition = cache.get(predicate)
            if cached_condition is None:
                condition = predicate(events)
                cache[predicate] = condition
                if condition:
                    handler(events)
            elif cached_condition is True:
                handler(events)
            else:
                pass


class EventHandlersNotEmptyError(Exception):
    pass


def assert_event_handlers_empty() -> None:
    """
    Raises EventHandlersNotEmptyError, unless
    there are no event handlers subscribed.
    """
    if len(_subscriptions):
        msg = "subscriptions still exist: %s" % _subscriptions
        raise EventHandlersNotEmptyError(msg)


def clear_event_handlers() -> None:
    """
    Removes all previously subscribed event handlers.
    """
    _subscriptions.clear()


def create_timesequenced_event_id() -> UUID:
    return uuid1()


class AbstractSnapshot(ActualOccasion):
    @property
    @abstractmethod
    def topic(self) -> str:
        """
        Path to the class of the snapshotted entity.
        """

    @property
    @abstractmethod
    def state(self) -> Dict[str, Any]:
        """
        State of the snapshotted entity.
        """

    @property
    @abstractmethod
    def originator_id(self) -> UUID:
        """
        ID of the snapshotted entity.
        """

    @property
    @abstractmethod
    def originator_version(self) -> int:
        """
        Version of the last event applied to the entity.
        """

    def __mutate__(self, obj: Optional[TEntity]) -> Optional[TEntity]:
        """
        Reconstructs the snapshotted entity.
        """
