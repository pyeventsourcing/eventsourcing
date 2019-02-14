from eventsourcing.application.policies import SnapshottingPolicy
from eventsourcing.application.simple import SimpleApplication
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.snapshotting import EventSourcedSnapshotStrategy


class SnapshottingApplication(SimpleApplication):
    # Todo: Change this to default to None?
    snapshot_period = 2

    def __init__(self, snapshot_period=None, snapshot_record_class=None, **kwargs):
        self.snapshot_period = snapshot_period or self.snapshot_period
        self.snapshot_record_class = snapshot_record_class
        self.snapshotting_policy = None
        self.snapshot_store = None
        self.snapshot_strategy = None
        self.snapshotting_policy = None
        super(SnapshottingApplication, self).__init__(**kwargs)

    def construct_event_store(self):
        super(SnapshottingApplication, self).construct_event_store()
        # Setup event store for snapshots.
        self.snapshot_store = EventStore(
            record_manager=self.infrastructure_factory.construct_snapshot_record_manager(),
            sequenced_item_mapper=self.sequenced_item_mapper_class(
                sequenced_item_class=self.sequenced_item_class
            )
        )

    def construct_repository(self, **kwargs):
        # Setup repository with a snapshot strategy.
        self.snapshot_strategy = EventSourcedSnapshotStrategy(
            snapshot_store=self.snapshot_store
        )
        super(SnapshottingApplication, self).construct_repository(
            snapshot_strategy=self.snapshot_strategy, **kwargs
        )

    def construct_persistence_policy(self):
        super(SnapshottingApplication, self).construct_persistence_policy()
        self.snapshotting_policy = SnapshottingPolicy(
            repository=self.repository,
            snapshot_store=self.snapshot_store,
            persist_event_type=self.persist_event_type,
            period=self.snapshot_period
        )

    def setup_table(self):
        super(SnapshottingApplication, self).setup_table()
        if self.datastore is not None:
            self.datastore.setup_table(self.snapshot_store.record_manager.record_class)

    def drop_table(self):
        super(SnapshottingApplication, self).drop_table()
        if self.datastore is not None:
            self.datastore.drop_table(self.snapshot_store.record_manager.record_class)

    def close(self):
        super(SnapshottingApplication, self).close()
        if self.snapshotting_policy is not None:
            self.snapshotting_policy.close()
            self.snapshotting_policy = None
