=====================
Everything in one app
=====================

In this example, an application is developed that includes all of
the aspects introduced in previous sections. The application has
aggregates with a root entity that controls a cluster of entities
and value objects, and which publishes events in batches. Aggregate
events are stored using Cassandra, with application level encryption,
and with snapshotting at regular intervals. The tests at the bottom
demonstrate that it works.


Domain
======

Aggregate model
---------------

.. code:: python

    from eventsourcing.domain.model.decorators import attribute
    from eventsourcing.domain.model.entity import TimestampedVersionedEntity
    from eventsourcing.domain.model.events import publish, subscribe, unsubscribe


    class ExampleAggregateRoot(TimestampedVersionedEntity):
        """
        Root entity of example aggregate.
        """
        class Event(TimestampedVersionedEntity.Event):
            """Supertype for events of example aggregates."""

        class Created(Event, TimestampedVersionedEntity.Created):
            """Published when aggregate is created."""

        class AttributeChanged(Event, TimestampedVersionedEntity.AttributeChanged):
            """Published when aggregate is changed."""

        class Discarded(Event, TimestampedVersionedEntity.Discarded):
            """Published when aggregate is discarded."""

        class ExampleCreated(Event):
            """Published when an "example" object in the aggregate is created."""
            def mutate(self, obj):
                entity = Example(example_id=self.example_id)
                obj._examples[str(entity.id)] = entity

        def __init__(self, foo, **kwargs):
            super(ExampleAggregateRoot, self).__init__(**kwargs)
            self._foo = foo
            self._pending_events = []
            self._examples = {}

        @attribute
        def foo(self):
            pass

        def count_examples(self):
            return len(self._examples)

        def create_new_example(self):
            self.__trigger_event__(
                ExampleAggregateRoot.ExampleCreated,
                example_id=uuid.uuid4()
            )

        def _publish(self, event):
            self._pending_events.append(event)

        def save(self):
            publish(self._pending_events[:])
            self._pending_events = []

        def discard(self):
            self.__dicard__()
            self.save()


    class Example(object):
        """
        Example entity. Controlled by aggregate root.

        Exists only within the aggregate boundary.
        """
        def __init__(self, example_id):
            self._id = example_id

        @property
        def id(self):
            return self._id


Aggregate factory
-----------------

.. code:: python

    def create_example_aggregate(foo):
        """
        Factory function for example aggregate.
        """
        return ExampleAggregateRoot.__create__(foo=foo)



Infrastructure
==============

.. code:: python

    from eventsourcing.infrastructure.cassandra.datastore import CassandraSettings, CassandraDatastore
    from eventsourcing.infrastructure.cassandra.activerecords import IntegerSequencedItemRecord, SnapshotRecord
    import uuid

    cassandra_datastore = CassandraDatastore(
        settings=CassandraSettings(),
        tables=(IntegerSequencedItemRecord, SnapshotRecord),
    )

    cassandra_datastore.setup_connection()
    cassandra_datastore.setup_tables()


Application
===========

Cipher strategy
---------------

.. code:: python

    from eventsourcing.utils.cipher.aes import AESCipher

    # Construct the cipher strategy.
    aes_key = b'0123456789abcdef'
    cipher = AESCipher(aes_key)


Snapshotting policy
-------------------

.. code:: python

    class ExampleSnapshottingPolicy(object):
        def __init__(self, example_repository, period=2):
            self.example_repository = example_repository
            self.period = period
            subscribe(predicate=self.trigger, handler=self.take_snapshot)

        def close(self):
            unsubscribe(predicate=self.trigger, handler=self.take_snapshot)

        def trigger(self, event):
            if isinstance(event, (list)):
                return True
            is_period = not (event.originator_version + 1) % self.period
            is_type = isinstance(event, ExampleAggregateRoot.Event)
            is_trigger = is_type and is_period
            return is_trigger

        def take_snapshot(self, event):
            if isinstance(event, list):
                for e in event:
                    if self.trigger(e):
                        self.take_snapshot(e)
            else:
                self.example_repository.take_snapshot(event.originator_id, lte=event.originator_version)

Application object
------------------

.. code:: python

    from eventsourcing.application.base import ApplicationWithPersistencePolicies
    from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
    from eventsourcing.infrastructure.snapshotting import EventSourcedSnapshotStrategy
    from eventsourcing.infrastructure.cassandra.activerecords import CassandraActiveRecordStrategy


    class EverythingApplication(ApplicationWithPersistencePolicies):

        def __init__(self, **kwargs):
            # Construct event stores and persistence policies.
            entity_active_record_strategy = CassandraActiveRecordStrategy(
                active_record_class=IntegerSequencedItemRecord,
            )
            snapshot_active_record_strategy = CassandraActiveRecordStrategy(
                active_record_class=SnapshotRecord,
            )
            super(EverythingApplication, self).__init__(
                entity_active_record_strategy=entity_active_record_strategy,
                snapshot_active_record_strategy=snapshot_active_record_strategy,
                **kwargs
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

        def close(self):
            super(EverythingApplication, self).close()
            self.snapshotting_policy.close()


Run the code
============

.. code:: python


    from eventsourcing.exceptions import ConcurrencyError


    with EverythingApplication(cipher=cipher, always_encrypt=True) as app:

        ## Check encryption.

        secret_aggregate = create_example_aggregate(foo='secret info')
        secret_aggregate.save()

        # With encryption enabled, application state is not visible in the database.
        event_store = app.entity_event_store

        item2 = event_store.active_record_strategy.get_item(secret_aggregate.id, eq=0)
        assert 'secret info' not in item2.data

        # Events are decrypted inside the application.
        retrieved_entity = app.example_repository[secret_aggregate.id]
        assert 'secret info' in retrieved_entity.foo


        ## Check concurrency control.

        aggregate = create_example_aggregate(foo='bar1')
        aggregate.create_new_example()

        aggregate.save()

        aggregate = app.example_repository[aggregate.id]
        assert aggregate.foo == 'bar1'
        assert aggregate.count_examples() == 1




        a = app.example_repository[aggregate.id]
        b = app.example_repository[aggregate.id]


        # Change the aggregate using instance 'a'.
        a.foo = 'bar2'
        a.save()
        assert app.example_repository[aggregate.id].foo == 'bar2'

        # Because 'a' has been changed since 'b' was obtained,
        # 'b' cannot be updated unless it is firstly refreshed.
        try:
            b.foo = 'bar3'
            b.save()
            assert app.example_repository[aggregate.id].foo == 'bar3'
        except ConcurrencyError:
            pass
        else:
            raise Exception("Failed to control concurrency of 'b':".format(app.example_repository[aggregate.id]))

        # Refresh object 'b', so that 'b' has the current state of the aggregate.
        b = app.example_repository[aggregate.id]
        assert b.foo == 'bar2'

        # Changing the aggregate using instance 'b' now works because 'b' is up to date.
        b.foo = 'bar3'
        b.save()
        assert app.example_repository[aggregate.id].foo == 'bar3'

        # Now 'a' does not have the current state of the aggregate, and cannot be changed.
        try:
            a.foo = 'bar4'
            a.save()
        except ConcurrencyError:
            pass
        else:
            raise Exception("Failed to control concurrency of 'a'.")


        ## Check snapshotting.

        # Create an aggregate.
        aggregate = create_example_aggregate(foo='bar1')
        aggregate.save()

        # Check there's no snapshot, only one event so far.
        snapshot = app.snapshot_strategy.get_snapshot(aggregate.id)
        assert snapshot is None

        # Change an attribute, generates a second event.
        aggregate.foo = 'bar2'
        aggregate.save()

        # Check the snapshot.
        snapshot = app.snapshot_strategy.get_snapshot(aggregate.id)
        assert snapshot.state['_foo'] == 'bar2'

        # Check can recover aggregate using snapshot.
        assert aggregate.id in app.example_repository
        assert app.example_repository[aggregate.id].foo == 'bar2'

        # Check snapshot after five events.
        aggregate.foo = 'bar3'
        aggregate.foo = 'bar4'
        aggregate.foo = 'bar5'
        aggregate.save()
        snapshot = app.snapshot_strategy.get_snapshot(aggregate.id)
        assert snapshot.state['_foo'] == 'bar4', snapshot.state['_foo']

        # Check snapshot after seven events.
        aggregate.foo = 'bar6'
        aggregate.foo = 'bar7'
        aggregate.save()
        assert app.example_repository[aggregate.id].foo == 'bar7'
        snapshot = app.snapshot_strategy.get_snapshot(aggregate.id)
        assert snapshot.state['_foo'] == 'bar6'

        # Check snapshot state is None after discarding the aggregate on the eighth event.
        aggregate.__discard__()
        aggregate.save()
        assert aggregate.id not in app.example_repository
        snapshot = app.snapshot_strategy.get_snapshot(aggregate.id)
        assert snapshot.state is None

        try:
            app.example_repository[aggregate.id]
        except KeyError:
            pass
        else:
            raise Exception('KeyError was not raised')

        # Get historical snapshots.
        snapshot = app.snapshot_strategy.get_snapshot(aggregate.id, lte=2)
        assert snapshot.state['___version__'] == 1  # one behind
        assert snapshot.state['_foo'] == 'bar2'

        snapshot = app.snapshot_strategy.get_snapshot(aggregate.id, lte=3)
        assert snapshot.state['___version__'] == 3
        assert snapshot.state['_foo'] == 'bar4'

        # Get historical entities.
        aggregate = app.example_repository.get_entity(aggregate.id, at=0)
        assert aggregate.__version__ == 0
        assert aggregate.foo == 'bar1', aggregate.foo

        aggregate = app.example_repository.get_entity(aggregate.id, at=1)
        assert aggregate.__version__ == 1
        assert aggregate.foo == 'bar2', aggregate.foo

        aggregate = app.example_repository.get_entity(aggregate.id, at=2)
        assert aggregate.__version__ == 2
        assert aggregate.foo == 'bar3', aggregate.foo

        aggregate = app.example_repository.get_entity(aggregate.id, at=3)
        assert aggregate.__version__ == 3
        assert aggregate.foo == 'bar4', aggregate.foo
