from uuid import uuid4

from eventsourcing.application.policies import PersistencePolicy
from eventsourcing.domain.model.entity import VersionedEntity
from eventsourcing.domain.model.events import assert_event_handlers_empty
from eventsourcing.domain.model.snapshot import Snapshot
from eventsourcing.example.domainmodel import Example, create_new_example
from eventsourcing.infrastructure.eventplayer import EventPlayer
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.sequenceditem import SequencedItem
from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
from eventsourcing.infrastructure.snapshotting import EventSourcedSnapshotStrategy, entity_from_snapshot
from eventsourcing.infrastructure.sqlalchemy.activerecords import SQLAlchemyActiveRecordStrategy, \
    IntegerSequencedItemRecord, SnapshotRecord
from eventsourcing.tests.datastore_tests.test_sqlalchemy import SQLAlchemyDatastoreTestCase


class TestEventPlayer(SQLAlchemyDatastoreTestCase):
    def setUp(self):
        assert_event_handlers_empty()
        super(TestEventPlayer, self).setUp()

        self.datastore.setup_connection()
        self.datastore.setup_tables()

        # Setup an event store for versioned entity events.
        self.entity_event_store = EventStore(
            active_record_strategy=SQLAlchemyActiveRecordStrategy(
                session=self.datastore.session,
                active_record_class=IntegerSequencedItemRecord,
                sequenced_item_class=SequencedItem,
            ),
            sequenced_item_mapper=SequencedItemMapper(
                sequenced_item_class=SequencedItem,
                sequence_id_attr_name='originator_id',
                position_attr_name='originator_version',
            ),
        )

        # Setup an event store for snapshots.
        self.snapshot_store = EventStore(
            active_record_strategy=SQLAlchemyActiveRecordStrategy(
                session=self.datastore.session,
                active_record_class=SnapshotRecord,
                sequenced_item_class=SequencedItem,
            ),
            sequenced_item_mapper=SequencedItemMapper(
                sequenced_item_class=SequencedItem,
                sequence_id_attr_name='originator_id',
                position_attr_name='originator_version',
            ),
        )
        self.entity_persistence_policy = None
        self.snapshot_persistence_policy = None

    def tearDown(self):
        self.datastore.drop_tables()
        self.datastore.drop_connection()
        if self.entity_persistence_policy is not None:
            self.entity_persistence_policy.close()
        if self.snapshot_persistence_policy is not None:
            self.snapshot_persistence_policy.close()
        super(TestEventPlayer, self).tearDown()
        assert_event_handlers_empty()

    def test_replay_entity(self):
        # Store example events.

        # Create entity1.
        entity_id1 = uuid4()
        event1 = Example.Created(originator_id=entity_id1, a=1, b=2)
        self.entity_event_store.append(event1)

        # Create entity2.
        entity_id2 = uuid4()
        event2 = Example.Created(originator_id=entity_id2, a=2, b=4)
        self.entity_event_store.append(event2)

        # Create entity3.
        entity_id3 = uuid4()
        event3 = Example.Created(originator_id=entity_id3, a=3, b=6)
        self.entity_event_store.append(event3)

        # Discard entity3.
        event4 = Example.Discarded(originator_id=entity_id3, originator_version=1)
        self.entity_event_store.append(event4)

        # Check the entities can be replayed.
        event_player = EventPlayer(event_store=self.entity_event_store, mutator=Example._mutate)

        # Check recovered entities have correct attribute values.
        recovered1 = event_player.replay_entity(entity_id1)
        self.assertEqual(entity_id1, recovered1.id)
        self.assertEqual(1, recovered1.a)

        recovered2 = event_player.replay_entity(entity_id2)
        self.assertEqual(2, recovered2.a)

        recovered3 = event_player.replay_entity(entity_id3)
        self.assertEqual(None, recovered3)

        # Check it works for "short" entities (should be faster, but the main thing is that it still works).
        # - just use a trivial mutate that always instantiates the 'Example'.
        event5 = Example.AttributeChanged(originator_id=entity_id1, originator_version=1, name='a', value=10)
        self.entity_event_store.append(event5)

        recovered1 = event_player.replay_entity(entity_id1)
        self.assertEqual(10, recovered1.a)

        event_player = EventPlayer(
            event_store=self.entity_event_store,
            mutator=Example._mutate,
            is_short=True,
        )
        self.assertEqual(10, event_player.replay_entity(entity_id1).a)

    def test_take_snapshot(self):
        self.entity_persistence_policy = PersistencePolicy(
            event_store=self.entity_event_store,
            event_type=VersionedEntity.Event,
        )
        self.snapshot_persistence_policy = PersistencePolicy(
            event_store=self.snapshot_store,
            event_type=Snapshot,
        )
        snapshot_strategy = EventSourcedSnapshotStrategy(
            event_store=self.snapshot_store
        )
        event_player = EventPlayer(
            event_store=self.entity_event_store,
            mutator=Example._mutate,
            snapshot_strategy=snapshot_strategy
        )

        # Take a snapshot with a non-existent ID.
        unregistered_id = uuid4()
        # Check no snapshot is taken.
        self.assertIsNone(event_player.take_snapshot(unregistered_id))
        # Check no snapshot is available.
        self.assertIsNone(event_player.get_snapshot(unregistered_id))

        # Create a new entity.
        registered_example = create_new_example(a=123, b=234)

        # Take a snapshot of the new entity (no previous snapshots).
        snapshot1 = event_player.take_snapshot(registered_example.id, lt=registered_example.version)

        # Check the snapshot is pegged to the last applied version.
        self.assertEqual(snapshot1.originator_version, 0)

        # Replay from this snapshot.
        entity_from_snapshot1 = entity_from_snapshot(snapshot1)
        retrieved_example = event_player.replay_entity(registered_example.id,
                                                       initial_state=entity_from_snapshot1,
                                                       gte=entity_from_snapshot1._version)

        # Check the attributes are correct.
        self.assertEqual(retrieved_example.a, 123)

        # Remember the version now.
        version1 = retrieved_example._version
        self.assertEqual(version1, 1)

        # Change attribute value.
        retrieved_example.a = 999

        # Remember the version now.
        version2 = retrieved_example._version
        self.assertEqual(version2, 2)

        # Change attribute value.
        retrieved_example.a = 9999

        # Remember the version now.
        version3 = retrieved_example._version
        self.assertEqual(version3, 3)

        # Check the event sourced entities are correct.
        retrieved_example = event_player.replay_entity(registered_example.id)
        self.assertEqual(retrieved_example.a, 9999)

        # Take another snapshot.
        snapshot2 = event_player.take_snapshot(retrieved_example.id, lt=retrieved_example.version)

        # Replay from this snapshot.
        initial_state = entity_from_snapshot(snapshot2)
        retrieved_example = event_player.replay_entity(
            registered_example.id,
            initial_state=initial_state,
            gte=initial_state._version,
        )
        # Check the attributes are correct.
        self.assertEqual(retrieved_example.a, 9999)

        # Check we can get historical state at version1.
        retrieved_example = event_player.replay_entity(registered_example.id, lt=version1)
        self.assertEqual(retrieved_example.a, 123)

        # Check we can get historical state at version2.
        retrieved_example = event_player.replay_entity(registered_example.id, lt=version2)
        self.assertEqual(retrieved_example.a, 999)

        # Check we can get historical state at version3.
        retrieved_example = event_player.replay_entity(registered_example.id, lt=version3)
        self.assertEqual(retrieved_example.a, 9999)

        # Similarly, check we can get historical state using a snapshot
        initial_state = entity_from_snapshot(snapshot1)
        retrieved_example = event_player.replay_entity(
            registered_example.id,
            initial_state=initial_state,
            gte=initial_state._version,
            lt=version2,
        )
        self.assertEqual(retrieved_example.a, 999)

        # Discard the entity.
        registered_example = event_player.replay_entity(registered_example.id)
        registered_example.discard()

        # Take snapshot of discarded entity.
        snapshot3 = event_player.take_snapshot(registered_example.id)
        self.assertIsNone(snapshot3.state)
        self.assertIsNone(entity_from_snapshot(snapshot3))
