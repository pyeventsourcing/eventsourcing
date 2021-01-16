from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, TypeVar, Union
from uuid import UUID

from eventsourcing.domain import Aggregate, Snapshot
from eventsourcing.persistence import (
    AbstractTranscoder,
    ApplicationRecorder,
    DatetimeAsISO,
    DecimalAsStr,
    EventStore,
    InfrastructureFactory,
    Mapper,
    Notification,
    Transcoder,
    UUIDAsHex,
)


class Repository:
    """Reconstructs aggregates from events in event store,
    possibly using snapshot store to avoid replaying all events."""
    def __init__(
        self,
        event_store: EventStore[Aggregate.Event],
        snapshot_store: Optional[EventStore[Snapshot]] = None,
    ):
        self.event_store = event_store
        self.snapshot_store = snapshot_store

    def get(self, aggregate_id: UUID, version: Optional[int] = None) -> Aggregate:
        """
        Returns aggregate for given ID, optionally at given version.
        """

        gt = None
        domain_events: List[Union[Snapshot, Aggregate.Event]] = []

        # Try to get a snapshot.
        if self.snapshot_store is not None:
            snapshots = self.snapshot_store.get(
                originator_id=aggregate_id,
                desc=True,
                limit=1,
                lte=version,
            )
            try:
                snapshot = next(snapshots)
                gt = snapshot.originator_version
                domain_events.append(snapshot)
            except StopIteration:
                pass

        # Get the domain events.
        domain_events += self.event_store.get(
            originator_id=aggregate_id,
            gt=gt,
            lte=version,
        )

        # Project the domain events.
        aggregate = None
        for domain_event in domain_events:
            aggregate = domain_event.mutate(aggregate)

        # Raise exception if not found.
        if aggregate is None:
            raise AggregateNotFound((aggregate_id, version))

        # Return the aggregate.
        assert isinstance(aggregate, Aggregate)
        return aggregate


@dataclass(frozen=True)
class Section:
    id: str
    items: List[Notification]
    next_id: Optional[str]


class AbstractNotificationLog(ABC):
    @abstractmethod
    def __getitem__(self, section_id: str) -> Section:
        """
        Returns section of notification log.
        """


class LocalNotificationLog(AbstractNotificationLog):
    DEFAULT_SECTION_SIZE = 10

    def __init__(
        self,
        recorder: ApplicationRecorder,
        section_size: int = DEFAULT_SECTION_SIZE,
    ):
        self.recorder = recorder
        self.section_size = section_size

    def __getitem__(self, section_id: str) -> Section:
        # Interpret the section ID.
        parts = section_id.split(",")
        part1 = int(parts[0])
        part2 = int(parts[1])
        start = max(1, part1)
        limit = min(max(0, part2 - start + 1), self.section_size)

        # Select notifications.
        notifications = self.recorder.select_notifications(start, limit)

        # Get next section ID.
        if len(notifications):
            last_id = notifications[-1].id
            return_id = self.format_section_id(notifications[0].id, last_id)
            if len(notifications) == limit:
                next_start = last_id + 1
                next_id = self.format_section_id(next_start, next_start + limit - 1)
            else:
                next_id = None
        else:
            return_id = None
            next_id = None

        # Return a section of the notification log.
        return Section(
            id=return_id,
            items=notifications,
            next_id=next_id,
        )

    @staticmethod
    def format_section_id(first, limit):
        return "{},{}".format(first, limit)


class Application(ABC):
    def __init__(self):
        self.factory = self.construct_factory()
        self.mapper = self.construct_mapper()
        self.recorder = self.construct_recorder()
        self.events = self.construct_event_store()
        self.snapshots = self.construct_snapshot_store()
        self.repository = self.construct_repository()
        self.log = self.construct_notification_log()

    def construct_factory(self) -> InfrastructureFactory:
        return InfrastructureFactory.construct(self.__class__.__name__)

    def construct_mapper(self, application_name="") -> Mapper:
        return self.factory.mapper(
            transcoder=self.construct_transcoder(),
            application_name=application_name,
        )

    def construct_transcoder(self) -> AbstractTranscoder:
        transcoder = Transcoder()
        self.register_transcodings(transcoder)
        return transcoder

    def register_transcodings(self, transcoder: Transcoder):
        """
        Registers transcoding objects on given transcoder.
        """
        transcoder.register(UUIDAsHex())
        transcoder.register(DecimalAsStr())
        transcoder.register(DatetimeAsISO())

    def construct_recorder(self) -> ApplicationRecorder:
        return self.factory.application_recorder()

    def construct_event_store(
        self,
    ) -> EventStore[Aggregate.Event]:
        return self.factory.event_store(
            mapper=self.mapper,
            recorder=self.recorder,
        )

    def construct_snapshot_store(
        self,
    ) -> Optional[EventStore[Snapshot]]:
        if not self.factory.is_snapshotting_enabled():
            return None
        recorder = self.factory.aggregate_recorder(purpose="snapshots")
        return self.factory.event_store(
            mapper=self.mapper,
            recorder=recorder,
        )

    def construct_repository(self) -> Repository:
        return Repository(
            event_store=self.events,
            snapshot_store=self.snapshots,
        )

    def construct_notification_log(self) -> LocalNotificationLog:
        return LocalNotificationLog(self.recorder, section_size=10)

    def save(self, *aggregates: Aggregate) -> None:
        """
        Collects pending events from given aggregates and
        puts them in the application's event store.
        """
        events = []
        for aggregate in aggregates:
            events += aggregate._collect_()
        self.events.put(events)
        self.notify(events)

    def notify(self, new_events: List[Aggregate.Event]):
        pass

    def take_snapshot(self, aggregate_id: UUID, version: Optional[int] = None):
        """
        Takes a snapshot of the recorded state of the aggregate,
        and puts the snapshot in the snapshot store.
        """
        aggregate = self.repository.get(aggregate_id, version)
        snapshot = Snapshot.take(aggregate)
        self.snapshots.put([snapshot])


TApplication = TypeVar("TApplication", bound=Application)


class AggregateNotFound(Exception):
    pass
