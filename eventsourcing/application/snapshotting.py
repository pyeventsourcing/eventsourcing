from eventsourcing.application.policies import SnapshottingPolicy
from eventsourcing.application.simple import SimpleApplication
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.snapshotting import EventSourcedSnapshotStrategy


class ApplicationWithSnapshotting(SimpleApplication):
    def __init__(self, snapshot_period=2, snapshot_record_class=None, **kwargs):
        self.snapshot_period = snapshot_period
        self.snapshot_record_class = snapshot_record_class
        self.snapshotting_policy = None
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

    def setup_repository(self, **kwargs):
        # Setup repository with a snapshot strategy.
        self.snapshot_strategy = EventSourcedSnapshotStrategy(
            snapshot_store=self.snapshot_store
        )
        super(ApplicationWithSnapshotting, self).setup_repository(
            snapshot_strategy=self.snapshot_strategy, **kwargs
        )

    def setup_persistence_policy(self):
        super(ApplicationWithSnapshotting, self).setup_persistence_policy()
        self.snapshotting_policy = SnapshottingPolicy(
            repository=self.repository,
            snapshot_store=self.snapshot_store,
            persist_event_type=self.persist_event_type,
            period=self.snapshot_period
        )

    def setup_table(self):
        super(ApplicationWithSnapshotting, self).setup_table()
        if self.datastore is not None:
            self.datastore.setup_table(self.snapshot_store.record_manager.record_class)

    def close(self):
        super(ApplicationWithSnapshotting, self).close()
        if self.snapshotting_policy is not None:
            self.snapshotting_policy.close()
            self.snapshotting_policy = None
