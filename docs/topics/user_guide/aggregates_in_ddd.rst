==================================
Aggregates in domain driven design
==================================

Eric Evans' book Domain Driven Design describes an abstraction called
"aggregate":

.. pull-quote::

    *An aggregate is a cluster of associated objects that we treat as a unit
    for the purpose of data changes. Each aggregate has a root and a boundary.*

Therefore,

    **Cluster the entities and value objects into aggregates and define
    boundaries around each. Choose one entity to be the root of each
    aggregate, and control all access to the objects inside the boundary
    through the root. Allow external objects to hold references to the
    root only.**

From this, it appears that an event sourced aggregate must have a set of
events and a mutator function that pertain to a cluster of objects within
a boundary. It must also have an entity that can function as the root of the
cluster of objects, with identity distinguishable across the application,
and with methods that exclusively operate on the objects of the aggregate.

Since one command may result in several events, it is also important never
to persist only some events that result from executing a command. And so
events must be appended to the event store in a single atomic transaction,
so that if some of the events resulting from executing a command cannot be
stored then none of them will be stored.


Aggregate root
--------------

To avoid duplicating code from previous examples, let's define an aggregate
root using classes from the library. The example aggregate root class below
has domain events that pertain to example objects in the aggregate, and methods
that can operate on the objects of the aggregate. There is a mutator
function, and a factory method that creates new aggregates.


.. code:: python

    from eventsourcing.domain.model.entity import TimestampedVersionedEntity
    from eventsourcing.infrastructure.eventstore import EventStore
    from eventsourcing.infrastructure.sqlalchemy.activerecords import SQLAlchemyActiveRecordStrategy
    from eventsourcing.example.domainmodel import Example


    class ExampleAggregateRoot(TimestampedVersionedEntity):
        """
        Root entity of example aggregate.
        """
        class Event(TimestampedVersionedEntity.Event):
            """Layer supertype."""

        class Created(Event, TimestampedVersionedEntity.Created):
            """Published when aggregate is created."""

        class Discarded(Event, TimestampedVersionedEntity.Discarded):
            """Published when aggregate is discarded."""

        class ExampleCreated(Event):
            """Published when an "example" object in the aggregate is created."""

        def __init__(self, **kwargs):
            super(ExampleAggregateRoot, self).__init__(**kwargs)
            self._pending_events = []
            self._examples = {}

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
            publish(self._pending_events[:])
            self._pending_events = []


    class Example(object):
        """
        Example domain entity in the example aggregate boundary.
        """
        def __init__(self, example_id):
            self._id = example_id

        @property
        def id(self):
            return self._id


    def mutate_aggregate(aggregate, event):
        """
        Mutator function for example aggregate.
        """

        # Handle "created" events by instantiating the aggregate class.
        if isinstance(event, ExampleAggregateRoot.Created):
            aggregate = ExampleAggregateRoot(**event.__dict__)
            aggregate._version += 1
            return aggregate

        # Handle "entity created" events by adding a new entity to the aggregate's dict of entities.
        elif isinstance(event, ExampleAggregateRoot.ExampleCreated):
            aggregate._assert_not_discarded()
            entity = Example(example_id=event.example_id)
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


Application and infrastructure
------------------------------

Setup infrastructure using library classes.

.. code:: python

    from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemySettings, SQLAlchemyDatastore
    from eventsourcing.infrastructure.sqlalchemy.activerecords import IntegerSequencedItemRecord

    datastore = SQLAlchemyDatastore(
        settings=SQLAlchemySettings(uri='sqlite:///:memory:'),
        tables=(IntegerSequencedItemRecord,),
    )

    datastore.setup_connection()
    datastore.setup_tables()


Define an application class that uses the model and infrastructure.

.. code:: python

    import uuid
    import time

    from eventsourcing.application.policies import PersistencePolicy
    from eventsourcing.domain.model.events import publish
    from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
    from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository


    class ExampleDDDApplication(object):
        def __init__(self, session):
            self.event_store = EventStore(
                active_record_strategy=SQLAlchemyActiveRecordStrategy(
                    session=session,
                    active_record_class=IntegerSequencedItemRecord,
                ),
                sequenced_item_mapper=SequencedItemMapper(
                    sequence_id_attr_name='originator_id',
                    position_attr_name='originator_version',
                )
            )
            self.aggregate_repository = EventSourcedRepository(
                event_store=self.event_store,
                mutator=mutate_aggregate,
            )
            self.persistence_policy = PersistencePolicy(
                event_store=self.event_store,
                event_type=ExampleAggregateRoot.Event
            )

        def create_example_aggregate(self):
            event = ExampleAggregateRoot.Created(originator_id=uuid.uuid4())
            aggregate = mutate_aggregate(aggregate=None, event=event)
            aggregate._pending_events.append(event)
            return aggregate

        def close(self):
            self.persistence_policy.close()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.close()


Run the code
------------

The application can be used to create new aggregates, and aggregates can be used to
create new entities. Events are published in batches when the aggregate's ``save()``
method is called.


.. code:: python

    with ExampleDDDApplication(datastore.session) as app:

        # Create a new aggregate.
        aggregate = app.create_example_aggregate()
        aggregate.save()

        # Check it exists in the repository.
        assert aggregate.id in app.aggregate_repository, aggregate.id

        # Check the aggregate has zero entities.
        assert aggregate.count_examples() == 0

        # Check the aggregate has zero entities.
        assert aggregate.count_examples() == 0

        # Ask the aggregate to create an entity within itself.
        aggregate.create_new_example()

        # Check the aggregate has one entity.
        assert aggregate.count_examples() == 1

        # Check the aggregate in the repo still has zero entities.
        assert app.aggregate_repository[aggregate.id].count_examples() == 0

        # Call save().
        aggregate.save()

        # Check the aggregate in the repo now has one entity.
        assert app.aggregate_repository[aggregate.id].count_examples() == 1

        # Create two more entities within the aggregate.
        aggregate.create_new_example()
        aggregate.create_new_example()

        # Save both "entity created" events in one atomic transaction.
        aggregate.save()

        # Check the aggregate in the repo now has three entities.
        assert app.aggregate_repository[aggregate.id].count_examples() == 3

        # Discard the aggregate, but don't call save() yet.
        aggregate.discard()

        # Check the aggregate still exists in the repo.
        assert aggregate.id in app.aggregate_repository

        # Call save().
        aggregate.save()

        # Check the aggregate no longer exists in the repo.
        assert aggregate.id not in app.aggregate_repository


The library has a slightly more sophisticated ``AggregateRoot`` class
that can be extended in the same way as the library's ``TimestampedVersionedEntity`` class,
from which it derives.
