from eventsourcing.application.policies import PersistencePolicy, SnapshottingPolicy
from eventsourcing.application.sqlalchemy import ApplicationWithSQLAlchemy
from eventsourcing.domain.model.entity import DomainEntity
from eventsourcing.domain.model.snapshot import Snapshot
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.snapshotting import EventSourcedSnapshotStrategy


class SnapshottingApplication(ApplicationWithSQLAlchemy):
    def __init__(self, period=10, snapshot_record_class=None, **kwargs):
        self.period = period
        self.snapshot_record_class = snapshot_record_class
        super(SnapshottingApplication, self).__init__(**kwargs)

    def setup_event_store(self):
        super(SnapshottingApplication, self).setup_event_store()
        # Setup event store for snapshots.
        record_manager = self.infrastructure_factory.construct_snapshot_record_manager()
        self.snapshot_store = EventStore(
            record_manager=record_manager,
            sequenced_item_mapper=self.sequenced_item_mapper_class(
                sequenced_item_class=self.sequenced_item_class
            )
        )

    def setup_table(self):
        super(SnapshottingApplication, self).setup_table()
        self.datastore.setup_table(self.snapshot_store.record_manager.record_class)

    def setup_repository(self, **kwargs):
        # Setup repository with a snapshot strategy.
        self.snapshot_strategy = EventSourcedSnapshotStrategy(
            event_store=self.snapshot_store
        )
        super(SnapshottingApplication, self).setup_repository(
            snapshot_strategy=self.snapshot_strategy, **kwargs
        )

    def setup_persistence_policy(self, persist_event_type):
        persist_event_type = persist_event_type or DomainEntity.Event
        super(SnapshottingApplication, self).setup_persistence_policy(persist_event_type)
        self.snapshotting_policy = SnapshottingPolicy(self.repository, self.period)
        self.snapshot_persistence_policy = PersistencePolicy(
            event_store=self.snapshot_store,
            event_type=Snapshot
        )

    def close(self):
        super(SnapshottingApplication, self).close()
        self.snapshotting_policy.close()
        self.snapshot_persistence_policy.close()
