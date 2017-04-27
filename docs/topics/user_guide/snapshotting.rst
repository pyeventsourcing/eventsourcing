============
Snapshotting
============

To enable snapshots to be used when recovering an entity from a
repository, construct an entity repository that has a snapshot
strategy object (see below).

It is recommended to store snapshots in a dedicated table.

To automatically generate snapshots, you could perhaps also
define a snapshotting policy, to take snapshots whenever a
particular condition occurs.


Domain
======

To avoid duplicating code from the previous section, let's
use the example entity class ``Example``, and its
factory ``create_new_example``, from the library.


.. code:: python

    from eventsourcing.example.domainmodel import Example, create_new_example


Infrastructure
==============

It is recommended not to store snapshots within the entity's sequence of events,
but in a dedicated table for snapshots. So let's setup a dedicated table
for snapshots, as well as a table for the events of the entity.

.. code:: python

    from eventsourcing.infrastructure.sqlalchemy.activerecords import IntegerSequencedItemRecord, SnapshotRecord
    from eventsourcing.infrastructure.sqlalchemy.datastore import ActiveRecord, SQLAlchemySettings, SQLAlchemyDatastore


    datastore = SQLAlchemyDatastore(
        settings=SQLAlchemySettings(uri='sqlite:///:memory:'),
        tables=(IntegerSequencedItemRecord, SnapshotRecord,),
    )

    datastore.setup_connection()
    datastore.setup_tables()


Application
===========


Policy
------

Now let's define a snapshotting policy object, so that snapshots
of example entities are taken every so many events.

The class ``ExampleSnapshottingPolicy`` below will take a snapshot of
the example entities every ``period`` number of events, so that there will
never be more than ``period`` number of events to replay when recovering the
entity. The default value of ``2`` is effective in the example below.

.. code:: python

    from eventsourcing.domain.model.events import subscribe, unsubscribe
    from eventsourcing.infrastructure.eventplayer import EventPlayer


    class ExampleSnapshottingPolicy(object):
        def __init__(self, example_repository, period=2):
            self.example_repository = example_repository
            self.period = period
            subscribe(predicate=self.triggers_snapshot, handler=self.take_snapshot)

        def close(self):
            unsubscribe(predicate=self.triggers_snapshot, handler=self.take_snapshot)

        def triggers_snapshot(self, event):
            return isinstance(event, Example.Event
            ) and not (event.originator_version + 1) % self.period

        def take_snapshot(self, event):
            self.example_repository.take_snapshot(event.originator_id, lte=event.originator_version)


Application object
------------------

The application class below extends the library class ``ApplicationWithPersistencePolicies``,
which constructs the event stores and persistence policies we need. The supertype has policy
to persist snapshots whenever they are taken, as well as a policy to persist the events of
the entity whenever they are published.

Below, the example entity repository ``example_repository`` is constructed from library class
``EventSourcedRepository`` with a snapshot strategy, the integer sequenced event
store, and a mutator function. The snapshot strategy is constructed from library class
``EventSourcedSnapshotStrategy`` with an event store for snapshots that is provided by the
supertype.

The application's snapshotting policy is constructed with the example repository, which
it needs to take snapshots.

.. code:: python

    from eventsourcing.application.base import ApplicationWithPersistencePolicies
    from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
    from eventsourcing.infrastructure.snapshotting import EventSourcedSnapshotStrategy
    from eventsourcing.infrastructure.sqlalchemy.activerecords import SQLAlchemyActiveRecordStrategy


    class SnapshottedApplication(ApplicationWithPersistencePolicies):

        def __init__(self, session):
            # Construct event stores and persistence policies.
            integer_sequenced_active_record_strategy = SQLAlchemyActiveRecordStrategy(
                active_record_class=IntegerSequencedItemRecord,
                session=session,
            )
            snapshot_active_record_strategy = SQLAlchemyActiveRecordStrategy(
                active_record_class=SnapshotRecord,
                session=datastore.session,
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
                example_repository=self.example_repository,
            )

        def create_new_example(self, foo):
            return create_new_example(foo=foo)

        def close(self):
            super(SnapshottedApplication, self).close()
            self.snapshotting_policy.close()


Run the code
============

The application object can be used in the same way as before. Now
snapshots of an example entity will be taken every second
event.

.. code:: python

    with SnapshottedApplication(datastore.session) as app:

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
