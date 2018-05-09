from eventsourcing.application.policies import SnapshottingPolicy, PersistencePolicy
from eventsourcing.application.simple import SimpleApplication
from eventsourcing.domain.model.entity import DomainEntity
from eventsourcing.domain.model.snapshot import Snapshot
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
from eventsourcing.infrastructure.snapshotting import EventSourcedSnapshotStrategy
from eventsourcing.infrastructure.sqlalchemy.manager import SQLAlchemyRecordManager
from eventsourcing.infrastructure.sqlalchemy.records import SnapshotRecord


class SnapshottingApplication(SimpleApplication):
    def __init__(self, period=10, snapshot_record_class=None, **kwargs):
        self.period = period
        self.snapshot_record_class = snapshot_record_class
        super(SnapshottingApplication, self).__init__(**kwargs)

    def setup_event_store(self):
        super(SnapshottingApplication, self).setup_event_store()
        # Setup snapshot store, using datastore session, and SnapshotRecord class.
        # Todo: Refactor this into a new create_sqlalchemy_snapshotstore() function.
        self.snapshot_store = EventStore(
            SQLAlchemyRecordManager(
                session=self.datastore.session,
                record_class=self.snapshot_record_class or SnapshotRecord
            ),
            SequencedItemMapper(
                sequence_id_attr_name='originator_id',
                position_attr_name='originator_version'
            )
        )

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

    def setup_table(self):
        super(SnapshottingApplication, self).setup_table()
        # Also setup snapshot table.
        self.datastore.setup_table(self.snapshot_store.record_manager.record_class)

    def close(self):
        super(SnapshottingApplication, self).close()
        self.snapshotting_policy.close()
        self.snapshot_persistence_policy.close()
