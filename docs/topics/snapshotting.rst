============
Snapshotting
============

Snapshots provide a fast path for obtaining the state of an entity or aggregate
that skips replaying some or all of the entity's events.

If the library repository class ``EventSourcedRepository`` is constructed with a
snapshot strategy object, it will try to get the closest snapshot to the required
version of a requested entity, and then replay only those events that will take
the snapshot up to the state at that version.

Snapshots can be taken manually. To automatically generate snapshots, a snapshotting
policy can take snapshots whenever a particular condition occurs, for example after
every ten events.

.. contents:: :local:


Domain
======

To avoid duplicating code from the previous sections, let's
use the example entity class :class:`~eventsourcing.example.domainmodel.Example`
and its factory function :func:`~eventsourcing.example.domainmodel.create_new_example`
from the library.

.. code:: python

    from eventsourcing.example.domainmodel import Example, create_new_example


Application
===========

The library class :class:`~eventsourcing.application.simple.SnapshottingApplication`,
extends :class:`~eventsourcing.application.simple.Application` by setting up
the application for snapshotting with a snapshot store, a dedicated table for
snapshots, and a policy to take snapshots every so many events. A separate
table is used for snapshot records.

.. code:: python

    from eventsourcing.application.snapshotting import SnapshottingApplication
    from eventsourcing.application.sqlalchemy import SQLAlchemyApplication

    class MyApplication(SQLAlchemyApplication, SnapshottingApplication):
        pass


Run the code
============

In the example below, snapshots of entities are taken every ``period`` number of
events.

.. code:: python

    with MyApplication(snapshot_period=2, persist_event_type=Example.Event) as app:

        # Create an entity.
        entity = create_new_example(foo='bar1')

        # Check there's no snapshot, only one event so far.
        snapshot = app.snapshot_strategy.get_snapshot(entity.id)
        assert snapshot is None

        # Change an attribute, generates a second event.
        entity.foo = 'bar2'

        # Check the snapshot.
        snapshot = app.snapshot_strategy.get_snapshot(entity.id)
        assert snapshot is not None
        assert snapshot.state['_foo'] == 'bar2'

        # Check can recover entity using snapshot.
        assert entity.id in app.repository
        assert app.repository[entity.id].foo == 'bar2'

        # Check snapshot after five events.
        entity.foo = 'bar3'
        entity.foo = 'bar4'
        entity.foo = 'bar5'
        snapshot = app.snapshot_strategy.get_snapshot(entity.id)
        assert snapshot.state['_foo'] == 'bar4'

        # Check snapshot after seven events.
        entity.foo = 'bar6'
        entity.foo = 'bar7'
        assert app.repository[entity.id].foo == 'bar7'
        snapshot = app.snapshot_strategy.get_snapshot(entity.id)
        assert snapshot.state['_foo'] == 'bar6'

        # Check snapshot state is None after discarding the entity on the eighth event.
        entity.__discard__()
        assert entity.id not in app.repository
        snapshot = app.snapshot_strategy.get_snapshot(entity.id)
        assert snapshot.state is None

        try:
            app.repository[entity.id]
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
        entity = app.repository.get_entity(entity.id, at=0)
        assert entity.__version__ == 0
        assert entity.foo == 'bar1', entity.foo

        entity = app.repository.get_entity(entity.id, at=1)
        assert entity.__version__ == 1
        assert entity.foo == 'bar2', entity.foo

        entity = app.repository.get_entity(entity.id, at=2)
        assert entity.__version__ == 2
        assert entity.foo == 'bar3', entity.foo

        entity = app.repository.get_entity(entity.id, at=3)
        assert entity.__version__ == 3
        assert entity.foo == 'bar4', entity.foo
