import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Generic, List, Mapping, Optional, Type, TypeVar
from uuid import UUID

from eventsourcing.domain import (
    Aggregate,
    AggregateEvent,
    Snapshot,
    TAggregate,
)
from eventsourcing.persistence import (
    ApplicationRecorder,
    DatetimeAsISO,
    DecimalAsStr,
    EventStore,
    InfrastructureFactory,
    JSONTranscoder,
    Mapper,
    Notification,
    Transcoder,
    UUIDAsHex,
)


class Repository(Generic[TAggregate]):
    """Reconstructs aggregates from events in an
    :class:`~eventsourcing.persistence.EventStore`,
    possibly using snapshot store to avoid replaying
    all events."""

    def __init__(
        self,
        event_store: EventStore[AggregateEvent],
        snapshot_store: Optional[EventStore[Snapshot]] = None,
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

    def get(self, aggregate_id: UUID, version: Optional[int] = None) -> TAggregate:
        """
        Returns an :class:`~eventsourcing.domain.Aggregate`
        for given ID, optionally at the given version.
        """

        aggregate: Optional[TAggregate] = None
        gt: Optional[int] = None

        if self.snapshot_store is not None:
            # Try to get a snapshot.
            snapshots = self.snapshot_store.get(
                originator_id=aggregate_id,
                desc=True,
                limit=1,
                lte=version,
            )
            try:
                snapshot = next(snapshots)
            except StopIteration:
                pass
            else:
                gt = snapshot.originator_version
                aggregate = snapshot.mutate()

        # Get aggregate events.
        domain_events = self.event_store.get(
            originator_id=aggregate_id,
            gt=gt,
            lte=version,
        )

        # Reconstruct the aggregate from its events.
        for domain_event in domain_events:
            aggregate = domain_event.mutate(aggregate)

        # Raise exception if "not found".
        if aggregate is None:
            raise AggregateNotFound((aggregate_id, version))
        else:
            # Return the aggregate.
            return aggregate


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
    as many notifications are were requested.

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
        Returns a :class:`Section` from a notification log.
        """

    @abstractmethod
    def select(self, start: int, limit: int) -> List[Notification]:
        """
        Returns a list of :class:`~eventsourcing.persistence.Notification` objects.
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
        requested section ID if there are less notifications
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

    def select(self, start: int, limit: int) -> List[Notification]:
        if limit > self.section_size:
            raise ValueError(
                f"Requested limit {limit} greater than section size {self.section_size}"
            )
        return self.recorder.select_notifications(start, limit)

    @staticmethod
    def format_section_id(first_id: int, last_id: int) -> str:
        return "{},{}".format(first_id, last_id)


class Application(ABC, Generic[TAggregate]):
    """
    Base class for event-sourced applications.
    """

    env: Mapping[str, str] = {}
    is_snapshotting_enabled: bool = False
    snapshotting_intervals: Optional[Dict[Type[Aggregate], int]] = None

    def __init__(self, env: Optional[Mapping] = None) -> None:
        """
        Initialises an application with an
        :class:`~eventsourcing.persistence.InfrastructureFactory`,
        a :class:`~eventsourcing.persistence.Mapper`,
        an :class:`~eventsourcing.persistence.ApplicationRecorder`,
        an :class:`~eventsourcing.persistence.EventStore`,
        a :class:`~eventsourcing.application.Repository`, and
        a :class:`~eventsourcing.application.LocalNotificationLog`.
        """
        self.env = self.construct_env(env)
        self.factory = self.construct_factory()
        self.mapper = self.construct_mapper()
        self.recorder = self.construct_recorder()
        self.events = self.construct_event_store()
        self.snapshots = self.construct_snapshot_store()
        self.repository = self.construct_repository()
        self.log = self.construct_notification_log()

    def construct_env(self, env: Optional[Mapping] = None) -> Mapping:
        """
        Constructs environment from which application will be configured.
        """
        _env = dict(type(self).env)
        if type(self).is_snapshotting_enabled or type(self).snapshotting_intervals:
            _env["IS_SNAPSHOTTING_ENABLED"] = "y"
        _env.update(os.environ)
        if env is not None:
            _env.update(env)
        return _env

    def construct_factory(self) -> InfrastructureFactory:
        """
        Constructs an :class:`~eventsourcing.persistence.InfrastructureFactory`
        for use by the application.
        """
        return InfrastructureFactory.construct(self.__class__.__name__, env=self.env)

    def construct_mapper(self, application_name: str = "") -> Mapper:
        """
        Constructs a :class:`~eventsourcing.persistence.Mapper`
        for use by the application.
        """
        return self.factory.mapper(
            transcoder=self.construct_transcoder(),
            application_name=application_name,
        )

    def construct_transcoder(self) -> Transcoder:
        """
        Constructs a :class:`~eventsourcing.persistence.Transcoder`
        for use by the application.
        """
        transcoder = JSONTranscoder()
        self.register_transcodings(transcoder)
        return transcoder

    # noinspection SpellCheckingInspection
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

    def construct_event_store(self) -> EventStore[AggregateEvent]:
        """
        Constructs an :class:`~eventsourcing.persistence.EventStore`
        for use by the application to store and retrieve aggregate
        :class:`~eventsourcing.domain.AggregateEvent` objects.
        """
        return self.factory.event_store(
            mapper=self.mapper,
            recorder=self.recorder,
        )

    def construct_snapshot_store(self) -> Optional[EventStore[Snapshot]]:
        """
        Constructs an :class:`~eventsourcing.persistence.EventStore`
        for use by the application to store and retrieve aggregate
        :class:`~eventsourcing.domain.Snapshot` objects.
        """
        if not self.factory.is_snapshotting_enabled():
            return None
        recorder = self.factory.aggregate_recorder(purpose="snapshots")
        return self.factory.event_store(
            mapper=self.mapper,
            recorder=recorder,
        )

    def construct_repository(self) -> Repository[TAggregate]:
        """
        Constructs a :class:`Repository` for use by the application.
        """
        return Repository(
            event_store=self.events,
            snapshot_store=self.snapshots,
        )

    def construct_notification_log(self) -> LocalNotificationLog:
        """
        Constructs a :class:`LocalNotificationLog` for use by the application.
        """
        return LocalNotificationLog(self.recorder, section_size=10)

    def save(self, *aggregates: Aggregate, **kwargs: Any) -> None:
        """
        Collects pending events from given aggregates and
        puts them in the application's event store.
        """
        # Collect and store events.
        events = []
        for aggregate in aggregates:
            events += aggregate.collect_events()
        self.events.put(events, **kwargs)

        # Take snapshots.
        if self.snapshots and self.snapshotting_intervals:
            aggregate_types = {}
            for aggregate in aggregates:
                aggregate_types[aggregate.id] = type(aggregate)
            for event in events:
                aggregate_type = aggregate_types[event.originator_id]
                interval = self.snapshotting_intervals.get(aggregate_type)
                if interval is not None:
                    if event.originator_version % interval == 0:
                        self.take_snapshot(
                            aggregate_id=event.originator_id,
                            version=event.originator_version,
                        )

        self.notify(events)

    def notify(self, new_events: List[AggregateEvent]) -> None:
        """
        Called after new domain events have been saved. This
        method on this class class doesn't actually do anything,
        but this method may be implemented by subclasses that
        need to take action when new domain events have been saved.
        """

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


TApplication = TypeVar("TApplication", bound=Application)


class AggregateNotFound(Exception):
    """
    Raised when an :class:`~eventsourcing.domain.Aggregate`
    object is not found in a :class:`Repository`.
    """
