============
Snapshotting
============

To enable snapshots to be used when recovering an entity from a
repository, construct an entity repository that has a snapshot
strategy object (see below). It is recommended to store snapshots
in a dedicated table.

To automatically generate snapshots, you could perhaps
define a snapshotting policy, to take snapshots whenever a
particular condition occurs.


Domain
======

To avoid duplicating code from the previous section, let's
use the example entity class :class:`~eventsourcing.example.domainmodel.Example`
and its factory function :func:`~eventsourcing.example.domainmodel.create_new_example`
from the library.


.. code:: python

    from eventsourcing.example.domainmodel import Example, create_new_example


Infrastructure
==============

It is recommended not to store snapshots within the entity's sequence of events,
but in a dedicated table for snapshots. So let's setup a dedicated table
for snapshots using the library class
:class:`~eventsourcing.infrastructure.sqlalchemy.activerecords.SnapshotRecord`,
as well as a table for the events of the entity.

.. code:: python

    from eventsourcing.infrastructure.sqlalchemy.activerecords import IntegerSequencedItemRecord, SnapshotRecord
    from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemyDatastore, SQLAlchemySettings


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


    class ExampleSnapshottingPolicy(object):
        def __init__(self, example_repository, period=2):
            self.example_repository = example_repository
            self.period = period
            subscribe(predicate=self.trigger, handler=self.take_snapshot)

        def close(self):
            unsubscribe(predicate=self.trigger, handler=self.take_snapshot)

        def trigger(self, event):
            return isinstance(event, Example.Event) and not (event.originator_version + 1) % self.period

        def take_snapshot(self, event):
            self.example_repository.take_snapshot(event.originator_id, lte=event.originator_version)


Because the event's ``originator_version`` is passed to the method ``take_snapshot()``,
with the argument ``lte``, the snapshot will reflect the entity as it existed just after
the event was applied. Even if a different thread operates on the same entity before the
snapshot is taken, the resulting snapshot is the same as it would have been otherwise.


Application object
------------------

The application class below extends the library class
:class:`~eventsourcing.application.base.ApplicationWithPersistencePolicies`,
which constructs the event stores and persistence policies we need. The supertype
has a policy to persist snapshots whenever they are taken. It also has as a policy
to persist the events of entities whenever they are published.

The example entity repository is constructed from library class
:class:`~eventsourcing.infrastructure.eventsourcedrepository.EventSourcedRepository`
with a snapshot strategy, the integer sequenced event store, and a mutator function.
The snapshot strategy is constructed from library class
:class:`~eventsourcing.infrastructure.snapshotting.EventSourcedSnapshotStrategy`
with an event store for snapshots that is provided by the supertype.

The application's snapshotting policy is constructed with the example repository, which
it needs in order to take snapshots.

.. code:: python

    from eventsourcing.application.base import ApplicationWithPersistencePolicies
    from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
    from eventsourcing.infrastructure.snapshotting import EventSourcedSnapshotStrategy
    from eventsourcing.infrastructure.sqlalchemy.activerecords import SQLAlchemyActiveRecordStrategy


    class SnapshottedApplication(ApplicationWithPersistencePolicies):

        def __init__(self, session):
            # Construct event stores and persistence policies.
            entity_active_record_strategy = SQLAlchemyActiveRecordStrategy(
                active_record_class=IntegerSequencedItemRecord,
                session=session,
            )
            snapshot_active_record_strategy = SQLAlchemyActiveRecordStrategy(
                active_record_class=SnapshotRecord,
                session=session,
            )
            super(SnapshottedApplication, self).__init__(
                entity_active_record_strategy=entity_active_record_strategy,
                snapshot_active_record_strategy=snapshot_active_record_strategy,
            )

            # Construct snapshot strategy.
            self.snapshot_strategy = EventSourcedSnapshotStrategy(
                event_store=self.snapshot_event_store
            )

            # Construct the entity repository, this time with the snapshot strategy.
            self.example_repository = EventSourcedRepository(
                event_store=self.entity_event_store,
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
        entity.__discard__()
        assert entity.id not in app.example_repository
        snapshot = app.snapshot_strategy.get_snapshot(entity.id)
        assert snapshot.state is None

        try:
            app.example_repository[entity.id]
        except KeyError:
            pass
        else:
            raise Exception('KeyError was not raised')

        # Get historical snapshots.
        snapshot = app.snapshot_strategy.get_snapshot(entity.id, lte=2)
        assert snapshot.state['___version__'] == 1  # one behind
        assert snapshot.state['_foo'] == 'bar2'

        snapshot = app.snapshot_strategy.get_snapshot(entity.id, lte=3)
        assert snapshot.state['___version__'] == 3
        assert snapshot.state['_foo'] == 'bar4'

        # Get historical entities.
        entity = app.example_repository.get_entity(entity.id, at=0)
        assert entity.__version__ == 0
        assert entity.foo == 'bar1', entity.foo

        entity = app.example_repository.get_entity(entity.id, at=1)
        assert entity.__version__ == 1
        assert entity.foo == 'bar2', entity.foo

        entity = app.example_repository.get_entity(entity.id, at=2)
        assert entity.__version__ == 2
        assert entity.foo == 'bar3', entity.foo

        entity = app.example_repository.get_entity(entity.id, at=3)
        assert entity.__version__ == 3
        assert entity.foo == 'bar4', entity.foo
