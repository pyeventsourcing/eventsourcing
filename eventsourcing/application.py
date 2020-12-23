from abc import ABC
from typing import List, Optional, TypeVar
from uuid import UUID

from eventsourcing.aggregate import (
    Aggregate,
)
from eventsourcing.eventmapper import (
    AbstractTranscoder,
    DatetimeAsISO,
    DecimalAsStr,
    Mapper,
    Transcoder,
    UUIDAsHex,
)
from eventsourcing.eventstore import EventStore
from eventsourcing.infrastructurefactory import (
    InfrastructureFactory,
)
from eventsourcing.notificationlog import LocalNotificationLog
from eventsourcing.recorders import ApplicationRecorder
from eventsourcing.repository import Repository

# Todo: Make a method to create a snapshot for an aggregate ID.
from eventsourcing.snapshotting import Snapshot


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
        return InfrastructureFactory.construct(
            self.__class__.__name__
        )

    def construct_mapper(
        self, application_name=""
    ) -> Mapper:
        return self.factory.mapper(
            transcoder=self.construct_transcoder(),
            application_name=application_name,
        )

    def construct_transcoder(self) -> AbstractTranscoder:
        transcoder = Transcoder()
        self.register_transcodings(transcoder)
        return transcoder

    def register_transcodings(
        self, transcoder: Transcoder
    ):
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
        recorder = self.factory.aggregate_recorder()
        return self.factory.event_store(
            mapper=self.mapper,
            recorder=recorder,
        )

    def construct_repository(self):
        return Repository(
            event_store=self.events,
            snapshot_store=self.snapshots,
        )

    def construct_notification_log(self):
        return LocalNotificationLog(
            self.recorder, section_size=10
        )

    def save(self, *aggregates: Aggregate) -> None:
        events = []
        for aggregate in aggregates:
            events += aggregate._collect_()
        self.events.put(events)
        self.notify(events)

    def notify(self, new_events: List[Aggregate.Event]):
        pass

    def take_snapshot(
        self, aggregate_id: UUID, version: int
    ):
        aggregate = self.repository.get(
            aggregate_id, version
        )
        snapshot = Snapshot.take(aggregate)
        self.snapshots.put([snapshot])


TApplication = TypeVar("TApplication", bound=Application)
