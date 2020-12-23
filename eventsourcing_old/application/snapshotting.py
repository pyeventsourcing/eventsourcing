from typing import Any, Optional

from eventsourcing.application.policies import SnapshottingPolicy
from eventsourcing.application.simple import SimpleApplication
from eventsourcing.domain.model.entity import TVersionedEntity, TVersionedEvent
from eventsourcing.domain.model.events import AbstractSnapshot
from eventsourcing.infrastructure.base import AbstractEventStore, AbstractRecordManager
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.snapshotting import EventSourcedSnapshotStrategy


class SnapshottingApplication(SimpleApplication[TVersionedEntity, TVersionedEvent]):
    snapshot_period = 0

    def __init__(self, snapshot_period: int = 0, **kwargs: Any):
        self.snapshot_period = snapshot_period or self.snapshot_period
        self.snapshot_store: Optional[
            AbstractEventStore[AbstractSnapshot, AbstractRecordManager]
        ] = None
        self.snapshot_strategy: Optional[EventSourcedSnapshotStrategy] = None
        self.snapshotting_policy: Optional[SnapshottingPolicy] = None
        super(SnapshottingApplication, self).__init__(**kwargs)

    def construct_event_store(self) -> None:
        super(SnapshottingApplication, self).construct_event_store()
        # Setup event store for snapshots.
        assert self.infrastructure_factory
        record_manager = self.infrastructure_factory.construct_snapshot_record_manager()
        assert self.sequenced_item_mapper_class is not None
        assert self.sequenced_item_class is not None

        self.snapshot_store = EventStore(
            record_manager=record_manager, event_mapper=self.event_store.event_mapper
        )

    def construct_repository(self, **kwargs: Any) -> None:
        # Setup repository with a snapshot strategy.
        assert self.snapshot_store
        self.snapshot_strategy = EventSourcedSnapshotStrategy(
            snapshot_store=self.snapshot_store
        )
        super(SnapshottingApplication, self).construct_repository(
            snapshot_strategy=self.snapshot_strategy, **kwargs
        )

    def construct_persistence_policy(self) -> None:
        super(SnapshottingApplication, self).construct_persistence_policy()
        assert self.snapshot_store
        self.snapshotting_policy = SnapshottingPolicy(
            repository=self.repository,
            snapshot_store=self.snapshot_store,
            persist_event_type=self.persist_event_type,
            period=self.snapshot_period,
        )

    def setup_table(self) -> None:
        super(SnapshottingApplication, self).setup_table()
        if self._datastore is not None:
            assert self.snapshot_store
            self._datastore.setup_table(self.snapshot_store.record_manager.record_class)

    def drop_table(self) -> None:
        super(SnapshottingApplication, self).drop_table()
        if self._datastore is not None:
            assert self.snapshot_store
            self._datastore.drop_table(self.snapshot_store.record_manager.record_class)

    def close(self) -> None:
        super(SnapshottingApplication, self).close()
        if self.snapshotting_policy is not None:
            self.snapshotting_policy.close()
            self.snapshotting_policy = None
