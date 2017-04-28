==========
Everything
==========

Domain
======


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



    from eventsourcing.domain.model.entity import attribute, TimestampedVersionedEntity
    from eventsourcing.domain.model.events import publish, subscribe, unsubscribe


    class ExampleAggregateRoot(TimestampedVersionedEntity):
        """
        Root entity of example aggregate.
        """
        class Event(TimestampedVersionedEntity.Event):
            """Layer supertype."""

        class Created(Event, TimestampedVersionedEntity.Created):
            """Published when aggregate is created."""

        class AttributeChanged(Event, TimestampedVersionedEntity.AttributeChanged):
            """Published when aggregate is changed."""

        class Discarded(Event, TimestampedVersionedEntity.Discarded):
            """Published when aggregate is discarded."""

        class ExampleCreated(Event):
            """Published when an "example" object in the aggregate is created."""

        class Example(object):
            """
            Example entity, exists only within the example aggregate boundary.
            """
            def __init__(self, example_id):
                self._id = example_id

            @property
            def id(self):
                return self._id

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
            assert not self._is_discarded
            event = ExampleAggregateRoot.ExampleCreated(
                example_id=uuid.uuid4(),
                originator_id=self.id,
                originator_version=self.version,
            )
            mutate_aggregate(self, event)
            self._publish(event)

        def _publish(self, event):
            self._pending_events.append(event)

        def save(self):
            #for e in self._pending_events:
            #    publish(e)
            publish(self._pending_events[:])
            self._pending_events = []



    def create_example_aggregate(foo):
        """
        Factory function for example aggregate.
        """
        # Construct event.
        event = ExampleAggregateRoot.Created(originator_id=uuid.uuid4(), foo=foo)

        # Mutate aggregate.
        aggregate = mutate_aggregate(aggregate=None, event=event)

        # Publish event to internal list only.
        aggregate._publish(event)

        # Return the new aggregate object.
        return aggregate




    def mutate_aggregate(aggregate, event):
        """
        Mutator function for example aggregate.
        """
        # Handle "created" events by constructing the aggregate object.
        if isinstance(event, ExampleAggregateRoot.Created):
            aggregate = ExampleAggregateRoot(**event.__dict__)
            aggregate._version += 1
            return aggregate

        # Handle "entity created" events by adding a new entity to the aggregate's dict of entities.
        elif isinstance(event, ExampleAggregateRoot.ExampleCreated):
            aggregate._assert_not_discarded()
            entity = ExampleAggregateRoot.Example(example_id=event.example_id)
            aggregate._examples[entity.id] = entity
            aggregate._version += 1
            aggregate._last_modified_on = event.timestamp
            return aggregate

        # Handle "discarded" events by returning 'None'.
        elif isinstance(event, ExampleAggregateRoot.Discarded):
            aggregate._assert_not_discarded()
            aggregate._version += 1
            aggregate._is_discarded = True
            return None
        else:
            raise NotImplementedError(type(event))




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
            #if event.originator_version not in [0, 1, 2, 3, 4]:
            #    raise Exception(event.originator_version, is_period, is_type, type(event))
            return is_trigger

        def take_snapshot(self, event):
            if isinstance(event, list):
                for e in event:
                    if self.trigger(e):
                        self.take_snapshot(e)
            else:
                self.example_repository.take_snapshot(event.originator_id, lte=event.originator_version)


    from eventsourcing.application.base import ApplicationWithPersistencePolicies
    from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
    from eventsourcing.infrastructure.snapshotting import EventSourcedSnapshotStrategy
    from eventsourcing.infrastructure.cassandra.activerecords import CassandraActiveRecordStrategy


    class EverythingApplication(ApplicationWithPersistencePolicies):

        def __init__(self, **kwargs):
            # Construct event stores and persistence policies.
            integer_sequenced_active_record_strategy = CassandraActiveRecordStrategy(
                active_record_class=IntegerSequencedItemRecord,
            )
            snapshot_active_record_strategy = CassandraActiveRecordStrategy(
                active_record_class=SnapshotRecord,
            )
            super(EverythingApplication, self).__init__(
                integer_sequenced_active_record_strategy=integer_sequenced_active_record_strategy,
                snapshot_active_record_strategy=snapshot_active_record_strategy,
                **kwargs
            )

            # Construct snapshot strategy.
            self.snapshot_strategy = EventSourcedSnapshotStrategy(
                event_store=self.snapshot_event_store
            )

            # Construct the entity repository, this time with the snapshot strategy.
            self.example_repository = EventSourcedRepository(
                event_store=self.integer_sequenced_event_store,
                mutator=ExampleAggregateRoot.mutate,
                snapshot_strategy=self.snapshot_strategy
            )

            # Construct the snapshotting policy.
            self.snapshotting_policy = ExampleSnapshottingPolicy(
                example_repository=self.example_repository,
            )

        def create_example_aggregate(self, foo):
            return create_example_aggregate(foo=foo)

        def close(self):
            super(EverythingApplication, self).close()
            self.snapshotting_policy.close()


    def construct_application(**kwargs):
        return EverythingApplication(**kwargs)


    from eventsourcing.domain.services.aes_cipher import AESCipher

    # Construct the cipher strategy.
    aes_key = '0123456789abcdef'
    cipher = AESCipher(aes_key)


    from eventsourcing.exceptions import ConcurrencyError


    with construct_application(cipher=cipher, always_encrypt=True) as app:

        ## Check encryption.
        secret_aggregate = app.create_example_aggregate(foo='secret info')
        secret_aggregate.save()

        # With encryption enabled, application state is not visible in the database.
        event_store = app.integer_sequenced_event_store

        item2 = event_store.active_record_strategy.get_item(secret_aggregate.id, eq=0)
        assert 'secret info' not in item2.data

        # Events are decrypted inside the application.
        retrieved_entity = app.example_repository[secret_aggregate.id]
        assert 'secret info' in retrieved_entity.foo


        ## Check concurrency control.

        entity = app.create_example_aggregate(foo='bar1')
        entity.save()
        assert app.example_repository[entity.id].foo == 'bar1'

        a = app.example_repository[entity.id]
        b = app.example_repository[entity.id]


        # Change the entity using instance 'a'.
        a.foo = 'bar2'
        a.save()
        assert app.example_repository[entity.id].foo == 'bar2'

        # Because 'a' has been changed since 'b' was obtained,
        # 'b' cannot be updated unless it is firstly refreshed.
        try:
            b.foo = 'bar3'
            b.save()
            assert app.example_repository[entity.id].foo == 'bar3'
        except ConcurrencyError:
            pass
        else:
            raise Exception("Failed to control concurrency of 'b':".format(app.example_repository[entity.id]))

        # Refresh object 'b', so that 'b' has the current state of the entity.
        b = app.example_repository[entity.id]
        assert b.foo == 'bar2'

        # Changing the entity using instance 'b' now works because 'b' is up to date.
        b.foo = 'bar3'
        b.save()
        assert app.example_repository[entity.id].foo == 'bar3'

        # Now 'a' does not have the current state of the entity, and cannot be changed.
        try:
            a.foo = 'bar4'
            a.save()
        except ConcurrencyError:
            pass
        else:
            raise Exception("Failed to control concurrency of 'a'.")


        ## Check snapshotting.

        # Create an entity.
        entity = app.create_example_aggregate(foo='bar1')
        entity.save()

        # Check there's no snapshot, only one event so far.
        snapshot = app.snapshot_strategy.get_snapshot(entity.id)
        assert snapshot is None

        # Change an attribute, generates a second event.
        entity.foo = 'bar2'
        entity.save()

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
        entity.save()
        snapshot = app.snapshot_strategy.get_snapshot(entity.id)
        assert snapshot.state['_foo'] == 'bar4', snapshot.state['_foo']

        # Check snapshot after seven events.
        entity.foo = 'bar6'
        entity.foo = 'bar7'
        entity.save()
        assert app.example_repository[entity.id].foo == 'bar7'
        snapshot = app.snapshot_strategy.get_snapshot(entity.id)
        assert snapshot.state['_foo'] == 'bar6'

        # Check snapshot state is None after discarding the entity on the eighth event.
        entity.discard()
        entity.save()
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
        assert snapshot.state['_version'] == 2  # one behind
        assert snapshot.state['_foo'] == 'bar2'

        snapshot = app.snapshot_strategy.get_snapshot(entity.id, lte=3)
        assert snapshot.state['_version'] == 4
        assert snapshot.state['_foo'] == 'bar4'

        # Get historical entities.
        entity = app.example_repository.get_entity(entity.id, lte=0)
        assert entity.version == 1
        assert entity.foo == 'bar1', entity.foo

        entity = app.example_repository.get_entity(entity.id, lte=1)
        assert entity.version == 2
        assert entity.foo == 'bar2', entity.foo

        entity = app.example_repository.get_entity(entity.id, lte=2)
        assert entity.version == 3
        assert entity.foo == 'bar3', entity.foo

        entity = app.example_repository.get_entity(entity.id, lte=3)
        assert entity.version == 4
        assert entity.foo == 'bar4', entity.foo
