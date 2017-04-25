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

From this, it seems to make an event sourced aggregate, we must have a set
of events and a mutator function that pertain to a cluster of objects within
a boundary. We must have an entity that can function as the root of the
aggregate, with identity distinguishable across the application, and with
methods that exclusively operate on the objects of the aggregate.

Since one command may result in several events, rather than publishing events
individually during the execution of a command, the operations of the aggregate
can instead append events to an internal list of pending events. A ``save()``
method can then publish all pending events as a single list.

The library supportsappending a list of events to the event store in a single
atomic transaction, so that if some of the events resulting from executing a
command cannot be stored then none of them will be stored.


Let's define an aggregate using events from the library.

The example below aggregate, with domain events that pertain
 to the objects
 of the
aggregate, a mutator function that can
mutate the objects of the aggregate, an aggregate root entity with methods that
operate on all the objects of the aggregate, and a factory method the creates new
aggregates.


.. code:: python

    from eventsourcing.domain.model.events import Created, Discarded, TimestampedVersionedEntityEvent
    from eventsourcing.infrastructure.eventstore import EventStore
    from eventsourcing.infrastructure.sqlalchemy.activerecords import SQLAlchemyActiveRecordStrategy
    from eventsourcing.example.domainmodel import Example


    class AggregateRoot(object):
        """
        Example root entity of aggregate.
        """
        def __init__(self, originator_id, originator_version=0, timestamp=None):
            self._id = originator_id
            self._version = originator_version
            self._is_discarded = False
            self._created_on = timestamp
            self._last_modified_on = timestamp
            self._pending_events = []
            self._entities = {}

        @property
        def id(self):
            return self._id

        @property
        def version(self):
            return self._version

        @property
        def is_discarded(self):
            return self._is_discarded

        @property
        def created_on(self):
            return self._created_on

        @property
        def last_modified_on(self):
            return self._last_modified_on

        def count_examples(self):
            return len(self._entities)

        def create_new_example(self):
            assert not self._is_discarded
            event = ExampleCreated(
                example_id=uuid.uuid4(),
                originator_id=self.id,
                originator_version=self.version,
            )
            mutate_aggregate(self, event)
            self._pending_events.append(event)

        def discard(self):
            assert not self._is_discarded
            event = Discarded(
                originator_id=self.id,
                originator_version=self.version
            )
            mutate_aggregate(self, event)
            self._pending_events.append(event)

        def save(self):
            publish(self._pending_events[:])
            self._pending_events = []



    class ExampleCreated(TimestampedVersionedEntityEvent):
        """
        Published when an entity is created.
        """
        def __init__(self, example_id, **kwargs):
            super(ExampleCreated, self).__init__(**kwargs)
            self.__dict__['example_id'] = example_id

        @property
        def example_id(self):
            return self.__dict__['example_id']


    class Example(object):
        """
        Example domain entity.
        """
        def __init__(self, example_id):
            self._id = example_id

        @property
        def id(self):
            return self._id


    def mutate_aggregate(aggregate, event):
        """
        Mutator function for example aggregate root.
        """

        # Handle "created" events by instantiating the aggregate class.
        if isinstance(event, Created):
            aggregate = AggregateRoot(**event.__dict__)
            aggregate._version += 1
            return aggregate

        # Handle "entity created" events by adding a new entity to the aggregate's dict of entities.
        elif isinstance(event, ExampleCreated):
            assert not aggregate.is_discarded
            entity = Example(example_id=event.example_id)
            aggregate._entities[entity.id] = entity
            aggregate._version += 1
            aggregate._last_modified_on = event.timestamp
            return aggregate

        # Handle "discarded" events by returning 'None'.
        elif isinstance(event, Discarded):
            assert not aggregate.is_discarded
            aggregate._version += 1
            aggregate._is_discarded = True
            return None
        else:
            raise NotImplementedError(type(event))



Setup infrastructure using library classes.

.. code:: python

    from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemySettings, SQLAlchemyDatastore
    from eventsourcing.infrastructure.sqlalchemy.activerecords import SqlIntegerSequencedItem

    datastore = SQLAlchemyDatastore(
        settings=SQLAlchemySettings(uri='sqlite:///:memory:'),
        tables=(SqlIntegerSequencedItem,),
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
        def __init__(self, datastore):
            self.event_store = EventStore(
                active_record_strategy=SQLAlchemyActiveRecordStrategy(
                    session=datastore.db_session,
                    active_record_class=SqlIntegerSequencedItem,
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
            self.persistence_policy = PersistencePolicy(self.event_store, event_type=TimestampedVersionedEntityEvent)

        def create_example_aggregate(self):
            event = Created(originator_id=uuid.uuid4())
            aggregate = mutate_aggregate(aggregate=None, event=event)
            aggregate._pending_events.append(event)
            return aggregate

        def close(self):
            self.persistence_policy.close()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.close()



The application can be used to create new aggregates, aggregates can be used to
create new entities. Batches of events are published and stored when the ``save()``
method is called.


.. code:: python

    with ExampleDDDApplication(datastore) as app:

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

        # Check the aggregate now has one entity.
        assert aggregate.count_examples() == 1

        # Check the aggregate in the repo now has one entity.
        assert app.aggregate_repository[aggregate.id].count_examples() == 1

        # Create two more entities within the aggregate.
        aggregate.create_new_example()
        aggregate.create_new_example()

        # Save both "entity created" events in one atomic transaction.
        aggregate.save()

        # Check the aggregate now has three entities.
        assert aggregate.count_examples() == 3, aggregate.count_examples()

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
that can be extended in the same way as the library's ``DomainEntity`` class,
from which it derives.
