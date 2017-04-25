============
Snapshotting
============

To enable snapshots to be used when recovering an entity from a
repository, construct the repository object with a snapshot
strategy object.

To automatically generate snapshots, you could perhaps define a policy
to take snapshots whenever a particular condition occurs.

Snapshotting policy
-------------------

Let's define a snapshotting policy, so that a snapshot is automatically
taken every few events.

The class ``ExampleSnapshottingPolicy`` below will take a snapshot of
an entity every ``period`` number of events, so that there will never
be more than ``period`` number of events to replay when recovering the
entity. The default value of ``2`` is effective in the example below.

.. code:: python

    from eventsourcing.infrastructure.eventplayer import EventPlayer
    from eventsourcing.domain.model.events import subscribe, unsubscribe


    class ExampleSnapshottingPolicy(object):
        def __init__(self, event_player, period=2):
            assert isinstance(event_player, EventPlayer)
            self.event_player = event_player
            self.period = period
            subscribe(predicate=self.triggers_snapshot, handler=self.take_snapshot)

        def close(self):
            unsubscribe(predicate=self.triggers_snapshot, handler=self.take_snapshot)

        def triggers_snapshot(self, event):
            return isinstance(
                event, TimestampedVersionedEntityEvent
            ) and not (
                event.originator_version + 1) % self.period

        def take_snapshot(self, event):
            self.event_player.take_snapshot(event.originator_id)


Infrastructure
--------------

Snapshots will be not be stored in the entity's sequence of events,
but in a dedicated table for snapshots.

Let's setup a dedicated table for snapshots.

.. code:: python

    from sqlalchemy.sql.schema import Column, Sequence, UniqueConstraint
    from eventsourcing.infrastructure.sqlalchemy.datastore import Base, SQLAlchemySettings, SQLAlchemyDatastore
    from eventsourcing.infrastructure.sqlalchemy.activerecords import IntegerSequencedItemRecord
    from sqlalchemy.sql.sqltypes import BigInteger, Integer, String, Text
    from sqlalchemy_utils import UUIDType


    class SnapshotRecord(Base):
        __tablename__ = 'snapshot'

        id = Column(Integer(), Sequence('snapshot_id_seq'), primary_key=True)
        sequence_id = Column(UUIDType(), index=True)
        position = Column(BigInteger(), index=True)
        topic = Column(String(255))
        data = Column(Text())
        __table_args__ = UniqueConstraint('sequence_id', 'position', name='snapshot_uc'),

    datastore = SQLAlchemyDatastore(
        settings=SQLAlchemySettings(uri='sqlite:///:memory:'),
        tables=(IntegerSequencedItemRecord, SnapshotRecord,),
    )

    datastore.setup_connection()
    datastore.setup_tables()


Application object
------------------

In the application class below extends the library class ``ApplicationWithPersistencePolicies``.

The ``EventSourcedRepository`` is constructed with an event sourced snapshot strategy.
The application also has a policy to persist snapshots whenever they are taken. The snapshotting policy is
configured to take a snapshot after each new event.

.. code:: python

    from eventsourcing.application.base import ApplicationWithPersistencePolicies
    from eventsourcing.domain.model.events import TimestampedVersionedEntityEvent
    from eventsourcing.example.domainmodel import Example, create_new_example
    from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
    from eventsourcing.infrastructure.snapshotting import EventSourcedSnapshotStrategy
    from eventsourcing.infrastructure.sqlalchemy.activerecords import SQLAlchemyActiveRecordStrategy


    class SnapshottedApplication(ApplicationWithPersistencePolicies):

        def __init__(self, datastore):
            # Construct event stores and persistence policies.
            integer_sequenced_active_record_strategy = SQLAlchemyActiveRecordStrategy(
                active_record_class=IntegerSequencedItemRecord,
                session=datastore.db_session,
            )
            snapshot_active_record_strategy = SQLAlchemyActiveRecordStrategy(
                active_record_class=SnapshotRecord,
                session=datastore.db_session,
            )
            super(SnapshottedApplication, self).__init__(
                integer_sequenced_active_record_strategy=integer_sequenced_active_record_strategy,
                snapshot_active_record_strategy=snapshot_active_record_strategy,
            )

            # Construct snapshot strategy.
            self.snapshot_strategy = EventSourcedSnapshotStrategy(
                event_store=self.snapshot_event_store
            )

            # Construct the entity repository, this time with the snapshot strategy.
            self.example_repository = EventSourcedRepository(
                event_store=self.integer_sequenced_event_store,
                mutator=Example.mutate,
                snapshot_strategy=self.snapshot_strategy
            )

            # Construct the snapshotting policy.
            self.snapshotting_policy = ExampleSnapshottingPolicy(
                event_player=self.example_repository.event_player,
            )

        def create_new_example(self, foo):
            return create_new_example(foo=foo)

        def close(self):
            super(SnapshottedApplication, self).close()
            self.snapshotting_policy.close()


Run the code
------------

Now snapshots of the example entity will be taken after every
event it publishes, including after both its created and discarded
events.

.. code:: python

    with SnapshottedApplication(datastore) as app:

        # Create an entity.
        entity = app.create_new_example(foo='bar1')

        # Check there's no snapshot, only one event so far.
        snapshot = app.snapshot_strategy.get_snapshot(entity.id)
        assert snapshot is None

        # Change an attribute, generates a second event.
        entity.foo = 'bar2'

        # Check the snapshot.
        snapshot = app.snapshot_strategy.get_snapshot(entity.id)
        assert snapshot.state['_foo'] == 'bar2'

        # Check can recover entity using snapshot.
        assert entity.id in app.example_repository
        assert app.example_repository[entity.id].foo == 'bar2'

        # Check snapshot after five events.
        entity.foo = 'bar3'
        entity.foo = 'bar4'
        entity.foo = 'bar5'
        snapshot = app.snapshot_strategy.get_snapshot(entity.id)
        assert snapshot.state['_foo'] == 'bar4'

        # Check snapshot after seven events.
        entity.foo = 'bar6'
        entity.foo = 'bar7'
        assert app.example_repository[entity.id].foo == 'bar7'
        snapshot = app.snapshot_strategy.get_snapshot(entity.id)
        assert snapshot.state['_foo'] == 'bar6'

        # Check snapshot state is None after discarding the entity on the eighth event.
        entity.discard()
        assert entity.id not in app.example_repository
        snapshot = app.snapshot_strategy.get_snapshot(entity.id)
        assert snapshot.state is None

        try:
            app.example_repository[entity.id]
        except KeyError:
            pass
        else:
            raise Exception('KeyError was not raised')

        # Get historical entities.
        entity = app.example_repository.get_entity(entity.id, lt=3)
        assert entity.version == 3
        assert entity.foo == 'bar3', entity.foo

        entity = app.example_repository.get_entity(entity.id, lt=4)
        assert entity.version == 4
        assert entity.foo == 'bar4', entity.foo

        # Get historical snapshots.
        snapshot = app.snapshot_strategy.get_snapshot(entity.id, lt=3)
        assert snapshot.state['_version'] == 2
        assert snapshot.state['_foo'] == 'bar2'

        snapshot = app.snapshot_strategy.get_snapshot(entity.id, lt=4)
        assert snapshot.state['_version'] == 4
        assert snapshot.state['_foo'] == 'bar4'
