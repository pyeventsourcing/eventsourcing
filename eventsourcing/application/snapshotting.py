from eventsourcing.application.policies import PersistencePolicy, SnapshottingPolicy
from eventsourcing.application.simple import SimpleApplication
from eventsourcing.domain.model.snapshot import Snapshot
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.snapshotting import EventSourcedSnapshotStrategy


class ApplicationWithSnapshotting(SimpleApplication):
    def __init__(self, period=10, snapshot_record_class=None, **kwargs):
        self.period = period
        self.snapshot_record_class = snapshot_record_class
        self.snapshotting_policy = None
        self.snapshot_persistence_policy = None
        super(ApplicationWithSnapshotting, self).__init__(**kwargs)

    def setup_event_store(self):
        super(ApplicationWithSnapshotting, self).setup_event_store()
        # Setup event store for snapshots.
        self.snapshot_store = EventStore(
            record_manager=self.infrastructure_factory.construct_snapshot_record_manager(),
            sequenced_item_mapper=self.sequenced_item_mapper_class(
                sequenced_item_class=self.sequenced_item_class
            )
        )

    def setup_table(self):
        super(ApplicationWithSnapshotting, self).setup_table()
        if self.datastore is not None:
            self.datastore.setup_table(self.snapshot_store.record_manager.record_class)

    def setup_repository(self, **kwargs):
        # Setup repository with a snapshot strategy.
        self.snapshot_strategy = EventSourcedSnapshotStrategy(
            event_store=self.snapshot_store
        )
        super(ApplicationWithSnapshotting, self).setup_repository(
            snapshot_strategy=self.snapshot_strategy, **kwargs
        )

    def setup_persistence_policy(self, *args, **kwargs):
        super(ApplicationWithSnapshotting, self).setup_persistence_policy(*args, **kwargs)
        self.snapshotting_policy = SnapshottingPolicy(self.repository, self.period)
        self.snapshot_persistence_policy = PersistencePolicy(
            event_store=self.snapshot_store,
            event_type=Snapshot
        )

    def close(self):
        super(ApplicationWithSnapshotting, self).close()
        if self.snapshotting_policy is not None:
            self.snapshotting_policy.close()
        if self.snapshot_persistence_policy is not None:
            self.snapshot_persistence_policy.close()
