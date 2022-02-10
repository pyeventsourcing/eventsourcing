import os
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass
from itertools import chain
from threading import Event, RLock
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterable,
    Iterator,
    List,
    Optional,
    Sequence,
    Type,
    TypeVar,
    Union,
    cast,
)
from uuid import UUID
from warnings import warn

from eventsourcing.domain import (
    Aggregate,
    AggregateEvent,
    DomainEvent,
    EventSourcingError,
    LogEvent,
    Snapshot,
    TAggregate,
    TLogEvent,
)
from eventsourcing.persistence import (
    ApplicationRecorder,
    DatetimeAsISO,
    DecimalAsStr,
    EventStore,
    InfrastructureFactory,
    Mapper,
    Notification,
    Recording,
    Tracking,
    Transcoder,
    UUIDAsHex,
)
from eventsourcing.utils import Environment, EnvType, strtobool

T = TypeVar("T")
ProjectorFunctionType = Callable[[Optional[T], Iterable[DomainEvent[T]]], Optional[T]]


def mutate_aggregate(
    aggregate: Optional[T], domain_events: Iterable[DomainEvent[T]]
) -> Optional[T]:
    """
    Mutator function for aggregate projections, which works
    by successively calling mutate() on each of the given
    list of domain events.
    """
    for domain_event in domain_events:
        aggregate = domain_event.mutate(aggregate)
    return aggregate


_S = TypeVar("_S")
_T = TypeVar("_T")


class Cache(Generic[_S, _T]):
    def __init__(self) -> None:
        self.cache: Dict[_S, Any] = {}

    def get(self, key: _S, evict: bool = False) -> _T:
        if evict:
            return self.cache.pop(key)
        else:
            return self.cache[key]

    def put(self, key: _S, value: _T) -> Optional[_T]:
        if value is not None:
            self.cache[key] = value
        return None


class LRUCache(Cache[_S, _T]):
    """
    Size limited caching that tracks accesses by recency.

    This is basically copied from functools.lru_cache. But
    we need to know when there was a cache hit, so we can
    fast-forward the aggregate with new stored events.
    """

    sentinel = object()  # unique object used to signal cache misses
    PREV, NEXT, KEY, RESULT = 0, 1, 2, 3  # names for the link fields

    def __init__(self, maxsize: int):
        # Constants shared by all lru cache instances:
        super().__init__()
        self.maxsize = maxsize
        self.full = False
        self.lock = RLock()  # because linkedlist updates aren't threadsafe
        self.root: List[Any] = []  # root of the circular doubly linked list
        self.clear()

    def clear(self) -> None:
        self.root[:] = [
            self.root,
            self.root,
            None,
            None,
        ]  # initialize by pointing to self

    def get(self, key: _S, evict: bool = False) -> _T:
        with self.lock:
            link = self.cache.get(key)
            if link is not None:
                link_prev, link_next, _key, result = link
                if not evict:
                    # Move the link to the front of the circular queue.
                    link_prev[self.NEXT] = link_next
                    link_next[self.PREV] = link_prev
                    last = self.root[self.PREV]
                    last[self.NEXT] = self.root[self.PREV] = link
                    link[self.PREV] = last
                    link[self.NEXT] = self.root
                else:
                    # Remove the link.
                    link_prev[self.NEXT] = link_next
                    link_next[self.PREV] = link_prev
                    del self.cache[key]
                    self.full = self.cache.__len__() >= self.maxsize

                return result
            else:
                raise KeyError

    def put(self, key: _S, value: _T) -> Optional[Any]:
        evicted_key = None
        evicted_value = None
        with self.lock:
            link = self.cache.get(key)
            if link is not None:
                # Set value.
                link[self.RESULT] = value
                # Move the link to the front of the circular queue.
                link_prev, link_next, _key, result = link
                link_prev[self.NEXT] = link_next
                link_next[self.PREV] = link_prev
                last = self.root[self.PREV]
                last[self.NEXT] = self.root[self.PREV] = link
                link[self.PREV] = last
                link[self.NEXT] = self.root
            elif self.full:
                # Use the old root to store the new key and result.
                oldroot = self.root
                oldroot[self.KEY] = key
                oldroot[self.RESULT] = value
                # Empty the oldest link and make it the new root.
                # Keep a reference to the old key and old result to
                # prevent their ref counts from going to zero during the
                # update. That will prevent potentially arbitrary object
                # clean-up code (i.e. __del__) from running while we're
                # still adjusting the links.
                self.root = oldroot[self.NEXT]
                evicted_key = self.root[self.KEY]
                evicted_value = self.root[self.RESULT]
                self.root[self.KEY] = self.root[self.RESULT] = None
                # Now update the cache dictionary.
                del self.cache[evicted_key]
                # Save the potentially reentrant cache[key] assignment
                # for last, after the root and links have been put in
                # a consistent state.
                self.cache[key] = oldroot
            else:
                # Put result in a new link at the front of the queue.
                last = self.root[self.PREV]
                link = [last, self.root, key, value]
                last[self.NEXT] = self.root[self.PREV] = self.cache[key] = link
                # Use the __len__() bound method instead of the len() function
                # which could potentially be wrapped in an lru_cache itself.
                self.full = self.cache.__len__() >= self.maxsize
        return evicted_key, evicted_value


class Repository:
    """Reconstructs aggregates from events in an
    :class:`~eventsourcing.persistence.EventStore`,
    possibly using snapshot store to avoid replaying
    all events."""

    def __init__(
        self,
        event_store: EventStore,
        snapshot_store: Optional[EventStore] = None,
        cache_maxsize: Optional[int] = None,
        fastforward: bool = True,
    ):
        """
        Initialises repository with given event store (an
        :class:`~eventsourcing.persistence.EventStore` for aggregate
        :class:`~eventsourcing.domain.AggregateEvent` objects)
        and optionally a snapshot store (an
        :class:`~eventsourcing.persistence.EventStore` for aggregate
        :class:`~eventsourcing.domain.Snapshot` objects).
        """
        self.event_store = event_store
        self.snapshot_store = snapshot_store

        if cache_maxsize is None:
            self.cache: Optional[Cache[UUID, Aggregate]] = None
        elif cache_maxsize <= 0:
            self.cache = Cache()
        else:
            self.cache = LRUCache(maxsize=cache_maxsize)
        self.fastforward = fastforward

    def get(
        self,
        aggregate_id: UUID,
        version: Optional[int] = None,
        projector_func: ProjectorFunctionType[Aggregate] = mutate_aggregate,
    ) -> Aggregate:
        if self.cache and version is None:
            try:
                # Look for aggregate in the cache.
                aggregate = self.cache.get(aggregate_id)
            except KeyError:
                # Reconstruct aggregate from stored events.
                aggregate = self._reconstruct_aggregate(
                    aggregate_id, projector_func=projector_func
                )
                # Put aggregate in the cache.
                self.cache.put(aggregate_id, aggregate)
            else:
                if self.fastforward:
                    # Fast-forward cached aggregate.
                    new_events = self.event_store.get(
                        originator_id=aggregate_id, gt=aggregate.version
                    )
                    _aggregate = projector_func(aggregate, new_events)
                    if _aggregate is None:
                        raise AggregateNotFound(aggregate_id)
                    else:
                        aggregate = _aggregate
            # Deep copy cached aggregate, so bad mutations don't corrupt cache.
            aggregate = deepcopy(aggregate)
        else:
            # Reconstruct historical version of aggregate from stored events.
            aggregate = self._reconstruct_aggregate(
                aggregate_id, version=version, projector_func=mutate_aggregate
            )
        return aggregate

    def _reconstruct_aggregate(
        self,
        aggregate_id: UUID,
        version: Optional[int] = None,
        projector_func: ProjectorFunctionType[Aggregate] = mutate_aggregate,
    ) -> Aggregate:
        """
        Reconstructs an :class:`~eventsourcing.domain.Aggregate` for a
        given ID from stored events, optionally at a particular version.
        """
        gt: Optional[int] = None

        if self.snapshot_store is not None:
            # Try to get a snapshot.
            snapshots = list(
                self.snapshot_store.get(
                    originator_id=aggregate_id,
                    desc=True,
                    limit=1,
                    lte=version,
                )
            )
            if snapshots:
                gt = snapshots[0].originator_version
        else:
            snapshots = []

        # Get aggregate events.
        aggregate_events = self.event_store.get(
            originator_id=aggregate_id,
            gt=gt,
            lte=version,
        )

        # Reconstruct the aggregate from its events.
        initial: Optional[Aggregate] = None
        aggregate = projector_func(initial, chain(snapshots, aggregate_events))

        # Raise exception if "not found".
        if aggregate is None:
            raise AggregateNotFound((aggregate_id, version))
        else:
            # Return the aggregate.
            return aggregate

    def __contains__(self, item: UUID) -> bool:
        try:
            self.get(aggregate_id=item)
        except AggregateNotFound:
            return False
        else:
            return True


@dataclass(frozen=True)
class Section:
    # noinspection PyUnresolvedReferences
    """
    Frozen dataclass that represents a section from a :class:`NotificationLog`.
    The :data:`items` attribute contains a list of
    :class:`~eventsourcing.persistence.Notification` objects.
    The :data:`id` attribute is the section ID, two integers
    separated by a comma that described the first and last
    notification ID that are included in the section.
    The :data:`next_id` attribute describes the section ID
    of the next section, and will be set if the section contains
    as many notifications as were requested.

    Constructor arguments:

    :param Optional[str] id: section ID of this section e.g. "1,10"
    :param List[Notification] items: a list of event notifications
    :param Optional[str] next_id: section ID of the following section
    """

    id: Optional[str]
    items: List[Notification]
    next_id: Optional[str]


class NotificationLog(ABC):
    """
    Abstract base class for notification logs.
    """

    @abstractmethod
    def __getitem__(self, section_id: str) -> Section:
        """
        Returns a :class:`Section` of
        :class:`~eventsourcing.persistence.Notification` objects
        from the notification log.
        """

    @abstractmethod
    def select(
        self,
        start: int,
        limit: int,
        stop: Optional[int] = None,
        topics: Sequence[str] = (),
    ) -> List[Notification]:
        """
        Returns a selection
        :class:`~eventsourcing.persistence.Notification` objects
        from the notification log.
        """


class LocalNotificationLog(NotificationLog):
    """
    Notification log that presents sections of event notifications
    retrieved from an :class:`~eventsourcing.persistence.ApplicationRecorder`.
    """

    DEFAULT_SECTION_SIZE = 10

    def __init__(
        self,
        recorder: ApplicationRecorder,
        section_size: int = DEFAULT_SECTION_SIZE,
    ):
        """
        Initialises a local notification object with given
        :class:`~eventsourcing.persistence.ApplicationRecorder`
        and an optional section size.

        Constructor arguments:

        :param ApplicationRecorder recorder: application recorder from which event
            notifications will be selected
        :param int section_size: number of notifications to include in a section

        """
        self.recorder = recorder
        self.section_size = section_size

    def __getitem__(self, requested_section_id: str) -> Section:
        """
        Returns a :class:`Section` of event notifications
        based on the requested section ID. The section ID of
        the returned section will describe the event
        notifications that are actually contained in
        the returned section, and may vary from the
        requested section ID if there are fewer notifications
        in the recorder than were requested, or if there
        are gaps in the sequence of recorded event notification.
        """
        # Interpret the section ID.
        parts = requested_section_id.split(",")
        part1 = int(parts[0])
        part2 = int(parts[1])
        start = max(1, part1)
        limit = min(max(0, part2 - start + 1), self.section_size)

        # Select notifications.
        notifications = self.select(start, limit)

        # Get next section ID.
        actual_section_id: Optional[str]
        next_id: Optional[str]
        if len(notifications):
            last_notification_id = notifications[-1].id
            actual_section_id = self.format_section_id(
                notifications[0].id, last_notification_id
            )
            if len(notifications) == limit:
                next_id = self.format_section_id(
                    last_notification_id + 1, last_notification_id + limit
                )
            else:
                next_id = None
        else:
            actual_section_id = None
            next_id = None

        # Return a section of the notification log.
        return Section(
            id=actual_section_id,
            items=notifications,
            next_id=next_id,
        )

    def select(
        self,
        start: int,
        limit: int,
        stop: Optional[int] = None,
        topics: Sequence[str] = (),
    ) -> List[Notification]:
        """
        Returns a selection
        :class:`~eventsourcing.persistence.Notification` objects
        from the notification log.
        """
        if limit > self.section_size:
            raise ValueError(
                f"Requested limit {limit} greater than section size {self.section_size}"
            )
        return self.recorder.select_notifications(
            start=start, limit=limit, stop=stop, topics=topics
        )

    @staticmethod
    def format_section_id(first_id: int, last_id: int) -> str:
        return "{},{}".format(first_id, last_id)


class ProcessingEvent:
    """
    Keeps together a :class:`~eventsourcing.persistence.Tracking`
    object, which represents the position of a domain event notification
    in the notification log of a particular application, and the
    new domain events that result from processing that notification.
    """

    def __init__(self, tracking: Optional[Tracking] = None):
        """
        Initialises the process event with the given tracking object.
        """
        self.tracking = tracking
        self.events: List[Union[AggregateEvent[Any], LogEvent]] = []
        self.aggregates: Dict[UUID, Aggregate] = {}
        self.saved_kwargs: Dict[Any, Any] = {}

    def collect_events(
        self,
        *objs: Optional[Union[Aggregate, AggregateEvent[Aggregate], LogEvent]],
        **kwargs: Any,
    ) -> None:
        """
        Collects pending domain events from the given aggregate.
        """
        for obj in objs:
            if isinstance(obj, (AggregateEvent, LogEvent)):
                self.events.append(obj)
            elif isinstance(obj, Aggregate):
                self.aggregates[obj.id] = obj
                for event in obj.collect_events():
                    self.events.append(event)
        self.saved_kwargs.update(kwargs)

    def save(
        self,
        *aggregates: Optional[Union[Aggregate, AggregateEvent[Aggregate]]],
        **kwargs: Any,
    ) -> None:
        warn(
            "'save()' is deprecated, use 'collect_events()' instead",
            DeprecationWarning,
            stacklevel=2,
        )

        self.collect_events(*aggregates, **kwargs)


class ProcessEvent(ProcessingEvent):
    """Deprecated, use :class:`ProcessingEvent` instead.

    Keeps together a :class:`~eventsourcing.persistence.Tracking`
    object, which represents the position of a domain event notification
    in the notification log of a particular application, and the
    new domain events that result from processing that notification.
    """

    def __init__(self, tracking: Optional[Tracking] = None):
        warn(
            "'ProcessEvent' is deprecated, use 'ProcessingEvent' instead",
            DeprecationWarning,
            stacklevel=2,
        )

        super().__init__(tracking)


class RecordingEvent:
    def __init__(
        self,
        application_name: str,
        recordings: List[Recording],
        previous_max_notification_id: Optional[int],
    ):
        self.application_name = application_name
        self.recordings = recordings
        self.previous_max_notification_id = previous_max_notification_id


class Application(ABC):
    """
    Base class for event-sourced applications.
    """

    name = "Application"
    env: EnvType = {}
    is_snapshotting_enabled: bool = False
    snapshotting_intervals: Optional[Dict[Type[Aggregate], int]] = None
    log_section_size = 10
    notify_topics: Sequence[str] = []

    AGGREGATE_CACHE_MAXSIZE = "AGGREGATE_CACHE_MAXSIZE"
    AGGREGATE_CACHE_FASTFORWARD = "AGGREGATE_CACHE_FASTFORWARD"

    def __init_subclass__(cls, **kwargs: Any) -> None:
        if "name" not in cls.__dict__:
            cls.name = cls.__name__

    def __init__(self, env: Optional[EnvType] = None) -> None:
        """
        Initialises an application with an
        :class:`~eventsourcing.persistence.InfrastructureFactory`,
        a :class:`~eventsourcing.persistence.Mapper`,
        an :class:`~eventsourcing.persistence.ApplicationRecorder`,
        an :class:`~eventsourcing.persistence.EventStore`,
        a :class:`~eventsourcing.application.Repository`, and
        a :class:`~eventsourcing.application.LocalNotificationLog`.
        """
        self.env = self.construct_env(self.name, env)
        self.factory = self.construct_factory(self.env)
        self.mapper = self.construct_mapper()
        self.recorder = self.construct_recorder()
        self.events = self.construct_event_store()
        self.snapshots: Optional[EventStore] = None
        if self.factory.is_snapshotting_enabled():
            self.snapshots = self.construct_snapshot_store()
        self.repository = self.construct_repository()
        self.notification_log = self.construct_notification_log()
        self.closing = Event()
        self.previous_max_notification_id: Optional[
            int
        ] = self.recorder.max_notification_id()

    @property
    def log(self) -> LocalNotificationLog:
        warn(
            "'log' is deprecated, use 'notifications' instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.notification_log

    def construct_env(self, name: str, env: Optional[EnvType] = None) -> Environment:
        """
        Constructs environment from which application will be configured.
        """
        _env = dict(type(self).env)
        if type(self).is_snapshotting_enabled or type(self).snapshotting_intervals:
            _env["IS_SNAPSHOTTING_ENABLED"] = "y"
        _env.update(os.environ)
        if env is not None:
            _env.update(env)
        return Environment(name, _env)

    def construct_factory(self, env: Environment) -> InfrastructureFactory:
        """
        Constructs an :class:`~eventsourcing.persistence.InfrastructureFactory`
        for use by the application.
        """
        return InfrastructureFactory.construct(env)

    def construct_mapper(self) -> Mapper:
        """
        Constructs a :class:`~eventsourcing.persistence.Mapper`
        for use by the application.
        """
        return self.factory.mapper(
            transcoder=self.construct_transcoder(),
        )

    def construct_transcoder(self) -> Transcoder:
        """
        Constructs a :class:`~eventsourcing.persistence.Transcoder`
        for use by the application.
        """
        transcoder = self.factory.transcoder()
        self.register_transcodings(transcoder)
        return transcoder

    def register_transcodings(self, transcoder: Transcoder) -> None:
        """
        Registers :class:`~eventsourcing.persistence.Transcoding`
        objects on given :class:`~eventsourcing.persistence.JSONTranscoder`.
        """
        transcoder.register(UUIDAsHex())
        transcoder.register(DecimalAsStr())
        transcoder.register(DatetimeAsISO())

    def construct_recorder(self) -> ApplicationRecorder:
        """
        Constructs an :class:`~eventsourcing.persistence.ApplicationRecorder`
        for use by the application.
        """
        return self.factory.application_recorder()

    def construct_event_store(self) -> EventStore:
        """
        Constructs an :class:`~eventsourcing.persistence.EventStore`
        for use by the application to store and retrieve aggregate
        :class:`~eventsourcing.domain.AggregateEvent` objects.
        """
        return self.factory.event_store(
            mapper=self.mapper,
            recorder=self.recorder,
        )

    def construct_snapshot_store(self) -> EventStore:
        """
        Constructs an :class:`~eventsourcing.persistence.EventStore`
        for use by the application to store and retrieve aggregate
        :class:`~eventsourcing.domain.Snapshot` objects.
        """
        recorder = self.factory.aggregate_recorder(purpose="snapshots")
        return self.factory.event_store(
            mapper=self.mapper,
            recorder=recorder,
        )

    def construct_repository(self) -> Repository:
        """
        Constructs a :class:`Repository` for use by the application.
        """
        cache_maxsize_envvar = self.env.get(self.AGGREGATE_CACHE_MAXSIZE)
        if cache_maxsize_envvar:
            cache_maxsize = int(cache_maxsize_envvar)
        else:
            cache_maxsize = None
        return Repository(
            event_store=self.events,
            snapshot_store=self.snapshots,
            cache_maxsize=cache_maxsize,
            fastforward=strtobool(self.env.get(self.AGGREGATE_CACHE_FASTFORWARD, "y")),
        )

    def construct_notification_log(self) -> LocalNotificationLog:
        """
        Constructs a :class:`LocalNotificationLog` for use by the application.
        """
        return LocalNotificationLog(self.recorder, section_size=self.log_section_size)

    def save(
        self,
        *objs: Optional[Union[TAggregate, AggregateEvent[Aggregate], LogEvent]],
        **kwargs: Any,
    ) -> List[Recording]:
        """
        Collects pending events from given aggregates and
        puts them in the application's event store.
        """
        processing_event = ProcessingEvent()
        processing_event.collect_events(*objs, **kwargs)
        recordings = self._record(processing_event)
        self._take_snapshots(processing_event)
        self._notify(recordings)
        self.notify(processing_event.events)  # Deprecated.
        return recordings

    def _record(self, processing_event: ProcessingEvent) -> List[Recording]:
        """
        Records given process event in the application's recorder.
        """
        recordings = self.events.put(
            processing_event.events,
            tracking=processing_event.tracking,
            **processing_event.saved_kwargs,
        )
        if self.repository.cache:
            for aggregate_id, aggregate in processing_event.aggregates.items():
                self.repository.cache.put(aggregate_id, aggregate)
        return recordings

    def _take_snapshots(self, processing_event: ProcessingEvent) -> None:
        # Take snapshots using IDs and types.
        if self.snapshots and self.snapshotting_intervals:
            for event in processing_event.events:
                try:
                    aggregate = processing_event.aggregates[event.originator_id]
                except KeyError:
                    continue
                interval = self.snapshotting_intervals.get(type(aggregate))
                if interval is not None:
                    if event.originator_version % interval == 0:
                        self.take_snapshot(
                            aggregate_id=event.originator_id,
                            version=event.originator_version,
                        )

    def take_snapshot(self, aggregate_id: UUID, version: Optional[int] = None) -> None:
        """
        Takes a snapshot of the recorded state of the aggregate,
        and puts the snapshot in the snapshot store.
        """
        if self.snapshots is None:
            raise AssertionError(
                "Can't take snapshot without snapshots store. Please "
                "set environment variable IS_SNAPSHOTTING_ENABLED to "
                "a true value (e.g. 'y'), or set 'is_snapshotting_enabled' "
                "on application class, or set 'snapshotting_intervals' on "
                "application class."
            )
        else:
            aggregate = self.repository.get(aggregate_id, version)
            snapshot = Snapshot.take(aggregate)
            self.snapshots.put([snapshot])

    def notify(
        self, new_events: List[Union[AggregateEvent[Aggregate], LogEvent]]
    ) -> None:
        """
        Deprecated.

        Called after new aggregate events have been saved. This
        method on this class doesn't actually do anything,
        but this method may be implemented by subclasses that
        need to take action when new domain events have been saved.
        """

    def _notify(self, recordings: List[Recording]) -> None:
        """
        Called after new aggregate events have been saved. This
        method on this class doesn't actually do anything,
        but this method may be implemented by subclasses that
        need to take action when new domain events have been saved.
        """

    def close(self) -> None:
        self.closing.set()
        self.factory.close()


TApplication = TypeVar("TApplication", bound=Application)


class AggregateNotFound(EventSourcingError):
    """
    Raised when an :class:`~eventsourcing.domain.Aggregate`
    object is not found in a :class:`Repository`.
    """


class EventSourcedLog(Generic[TLogEvent]):
    """
    Constructs a sequence of domain events, like an aggregate.
    But unlike an aggregate the events can be triggered
    and selected for use in an application without
    reconstructing a current state from all the events.

    This allows an indefinitely long sequence of events to be
    generated and used without the practical restrictions of
    projecting the events into a current state before they
    can be used, which is useful e.g. for logging and
    progressively discovering all the aggregate IDs of a
    particular type in an application.
    """

    def __init__(
        self,
        events: EventStore,
        originator_id: UUID,
        logged_cls: Type[TLogEvent],
    ):
        self.events = events
        self.originator_id = originator_id
        self.logged_cls = logged_cls

    def trigger_event(
        self, next_originator_version: Optional[int] = None, **kwargs: Any
    ) -> TLogEvent:
        """
        Constructs and returns a new log event.
        """
        if next_originator_version is None:
            last_logged = self.get_last()
            if last_logged is None:
                next_originator_version = Aggregate.INITIAL_VERSION
            else:
                next_originator_version = last_logged.originator_version + 1

        return self.logged_cls(  # type: ignore
            originator_id=self.originator_id,
            originator_version=next_originator_version,
            timestamp=self.logged_cls.create_timestamp(),
            **kwargs,
        )

    def get_first(self) -> Optional[TLogEvent]:
        """
        Selects the first logged event.
        """
        try:
            return next(self.get(limit=1))
        except StopIteration:
            return None

    def get_last(self) -> Optional[TLogEvent]:
        """
        Selects the last logged event.
        """
        try:
            return next(self.get(desc=True, limit=1))
        except StopIteration:
            return None

    def get(
        self,
        gt: Optional[int] = None,
        lte: Optional[int] = None,
        desc: bool = False,
        limit: Optional[int] = None,
    ) -> Iterator[TLogEvent]:
        """
        Selects a range of logged events with limit,
        with ascending or descending order.
        """
        return cast(
            Iterator[TLogEvent],
            self.events.get(
                originator_id=self.originator_id,
                gt=gt,
                lte=lte,
                desc=desc,
                limit=limit,
            ),
        )
