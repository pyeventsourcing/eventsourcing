============
Snapshotting
============

To enable snapshotting, pass in a snapshotting strategy object when constructing
an entity repository.

Firstly setup a dedicated table for snapshots.

.. code:: python

    from sqlalchemy.sql.schema import Column, Sequence, UniqueConstraint
    from eventsourcing.infrastructure.sqlalchemy.datastore import Base, SQLAlchemySettings, SQLAlchemyDatastore
    from eventsourcing.infrastructure.sqlalchemy.activerecords import SqlIntegerSequencedItem
    from sqlalchemy.sql.sqltypes import BigInteger, Integer, String, Text
    from sqlalchemy_utils import UUIDType


    class SnapshotTable(Base):
        __tablename__ = 'snapshot'

        id = Column(Integer(), Sequence('snapshot_id_seq'), primary_key=True)
        sequence_id = Column(UUIDType(), index=True)
        position = Column(BigInteger(), index=True)
        topic = Column(String(255))
        data = Column(Text())
        __table_args__ = UniqueConstraint('sequence_id', 'position',
                                          name='integer_sequenced_item_uc'),

    datastore = SQLAlchemyDatastore(
        settings=SQLAlchemySettings(uri='sqlite:///:memory:'),
    )

    datastore.setup_connection()
    datastore.setup_tables()


Let's introduce a snapshotting policy, so that a snapshot is automatically
taken at a regular intervals.

.. code:: python

    from eventsourcing.infrastructure.eventplayer import EventPlayer
    from eventsourcing.domain.model.events import subscribe, unsubscribe


    class SnapshottingPolicy(object):
        def __init__(self, event_player, frequency):
            assert isinstance(event_player, EventPlayer)
            self.event_player = event_player
            self.frequency = frequency
            subscribe(predicate=self.triggers_snapshot, handler=self.take_snapshot)

        def close(self):
            unsubscribe(predicate=self.triggers_snapshot, handler=self.take_snapshot)

        def triggers_snapshot(self, event):
            return isinstance(event, TimestampedVersionedEntityEvent) and not (event.originator_version + 1) % self.frequency

        def take_snapshot(self, event):
            self.event_player.take_snapshot(event.originator_id)



In the application class below, the ``EventSourcedRepository`` is constructed with
an event sourced snapshot strategy. The application also has a policy to persist
snapshots whenever they are taken. The snapshotting policy is configured to take
a snapshot after each new event.

.. code:: python

    from eventsourcing.application.policies import PersistencePolicy
    from eventsourcing.domain.model.snapshot import Snapshot
    from eventsourcing.infrastructure.eventstore import EventStore
    from eventsourcing.infrastructure.snapshotting import EventSourcedSnapshotStrategy
    from eventsourcing.infrastructure.sqlalchemy.activerecords import SQLAlchemyActiveRecordStrategy
    from eventsourcing.infrastructure.sequenceditem import SequencedItem
    from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
    from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
    from eventsourcing.example.domainmodel import Example, create_new_example
    from eventsourcing.domain.model.events import TimestampedVersionedEntityEvent


    class SnapshottedApplication(object):

        def __init__(self, datastore):
            self.event_store = EventStore(
                active_record_strategy=SQLAlchemyActiveRecordStrategy(
                    session=datastore.db_session,
                    active_record_class=SqlIntegerSequencedItem,
                    sequenced_item_class=SequencedItem
                ),
                sequenced_item_mapper=SequencedItemMapper(
                    sequenced_item_class=SequencedItem,
                    sequence_id_attr_name='originator_id',
                    position_attr_name='originator_version'
                )
            )
            self.snapshot_store = EventStore(
                active_record_strategy=SQLAlchemyActiveRecordStrategy(
                    session=datastore.db_session,
                    active_record_class=SnapshotTable,
                    sequenced_item_class=SequencedItem
                ),
                sequenced_item_mapper=SequencedItemMapper(
                    sequenced_item_class=SequencedItem,
                    sequence_id_attr_name='originator_id',
                    position_attr_name='originator_version'
                )
            )

            # Construct a snapshot strategy.
            self.snapshot_strategy = EventSourcedSnapshotStrategy(
                event_store=self.snapshot_store
            )

            # Construct the repository with the snapshot strategy.
            self.example_repository = EventSourcedRepository(
                event_store=self.event_store,
                mutator=Example.mutate,
                snapshot_strategy=self.snapshot_strategy
            )

            # Construct the persistence policies.
            self.entity_persistence_policy = PersistencePolicy(
                event_store=self.event_store,
                event_type=TimestampedVersionedEntityEvent
            )
            self.snapshot_persistence_policy = PersistencePolicy(
                event_store=self.snapshot_store,
                event_type=Snapshot
            )

            # Construct the snapshotting policy.
            self.snapshotting_policy = SnapshottingPolicy(
                event_player=self.example_repository.event_player,
                frequency=1
            )

        def create_new_example(self, foo):
            return create_new_example(foo=foo)

        def close(self):
            self.entity_persistence_policy.close()
            self.snapshot_persistence_policy.close()
            self.snapshotting_policy.close()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.close()


Now snapshots of the example entity will be taken after every
event it publishes, including after both its created and discarded
events.

.. code:: python

    with SnapshottedApplication(datastore) as app:

        entity = app.create_new_example(foo='bar1')

        snapshot = app.snapshot_strategy.get_snapshot(entity.id)
        assert snapshot.state['_foo'] == 'bar1'

        assert entity.id in app.example_repository

        assert app.example_repository[entity.id].foo == 'bar1'

        entity.foo = 'bar2'
        entity.foo = 'bar3'
        entity.foo = 'bar4'
        entity.foo = 'bar5'
        snapshot = app.snapshot_strategy.get_snapshot(entity.id)
        assert snapshot.state['_foo'] == 'bar5'

        entity.foo = 'bar6'
        entity.foo = 'bar7'
        assert app.example_repository[entity.id].foo == 'bar7'

        snapshot = app.snapshot_strategy.get_snapshot(entity.id)
        assert snapshot.state['_foo'] == 'bar7'

        # Discard the entity.
        entity.discard()

        snapshot = app.snapshot_strategy.get_snapshot(entity.id)
        assert snapshot.state is None

        assert entity.id not in app.example_repository

        try:
            app.example_repository[entity.id]
        except KeyError:
            pass
        else:
            raise Exception('KeyError was not raised')
