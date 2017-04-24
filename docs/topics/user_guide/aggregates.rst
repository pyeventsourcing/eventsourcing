==================================
Aggregates in domain driven design
==================================

Eric Evans' book Domain Driven Design describes an abstraction called
"aggregate".

.. pull-quote::

    An aggregate is a cluster of associated objects that we treat as a unit
    for the purpose of data changes. Each aggregate has a root and a boundary.

Therefore,

    Cluster the entities and value objects into aggregates and define
    boundaries around each. Choose one entity to be the root of each
    aggregate, and control all access to the objects inside the boundary
    through the root. Allow external objects to hold references to the
    root only.

Hence to make an event sourced aggregate, we must have a set of events and a
mutator function that pertains to a cluster of objects within the aggregate
boundary. We must have an entity that can function as the root of the aggregate,
with identity distinguishable across the application, and with methods that
exclusively operate on the objects of the aggregate.

The example below demonstrates a stand-alone domain model aggregate, with domain
events that pertain to the objects of the aggregate, a mutator function that can
mutate the objects of the aggregate, an aggregate root entity with methods that
operate all the objects of the aggregate, and a factory method the creates new
aggregates.

Rather than publishing events immediately and individually during the execution
of a command, the operations of the aggregate root class below append events to
an internal list of pending events. Its ``save()`` method can then publish all
pending events as a single list. The library supports appending a list of events
to the event store in a single atomic transaction, so that if some of the events
resulting from executing a command cannot be stored then none of them will be stored.

.. code:: python

    from eventsourcing.infrastructure.eventstore import EventStore
    from eventsourcing.infrastructure.sqlalchemy.activerecords import SQLAlchemyActiveRecordStrategy
    from eventsourcing.example.domainmodel import Example


    class AggregateEvent(object):
        """
        Layer supertype.
        """
        def __init__(self, aggregate_id, aggregate_version, timestamp=None, **kwargs):
            self.aggregate_id = aggregate_id
            self.aggregate_version = aggregate_version
            self.timestamp = timestamp or time.time()
            self.__dict__.update(kwargs)


    class AggregateCreated(AggregateEvent):
        """
        Published when an aggregate is created.
        """
        def __init__(self, aggregate_version=0, **kwargs):
            super(AggregateCreated, self).__init__(aggregate_version=aggregate_version, **kwargs)


    class EntityCreated(AggregateEvent):
        """
        Published when an entity is created.
        """
        def __init__(self, entity_id, **kwargs):
            super(EntityCreated, self).__init__(entity_id=entity_id, **kwargs)


    class AggregateDiscarded(AggregateEvent):
        """
        Published when an aggregate is discarded.
        """
        def __init__(self, **kwargs):
            super(AggregateDiscarded, self).__init__(**kwargs)


    class AggregateRoot():
        """
        Example root entity of aggregate.
        """
        def __init__(self, aggregate_id, aggregate_version=0, timestamp=None):
            self._id = aggregate_id
            self._version = aggregate_version
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

        def count_entities(self):
            return len(self._entities)

        def create_new_entity(self):
            assert not self._is_discarded
            event = EntityCreated(
                entity_id=uuid.uuid4(),
                aggregate_id=self.id,
                aggregate_version=self.version,
            )
            mutate_aggregate_event(self, event)
            self._pending_events.append(event)

        def discard(self):
            assert not self._is_discarded
            event = AggregateDiscarded(aggregate_id=self.id, aggregate_version=self.version)
            mutate_aggregate_event(self, event)
            self._pending_events.append(event)

        def save(self):
            publish(self._pending_events[:])
            self._pending_events = []


    class Example(object):
        """
        Example domain entity.
        """
        def __init__(self, entity_id):
            self._id = entity_id

        @property
        def id(self):
            return self._id


    def mutate_aggregate_event(aggregate, event):
        """
        Mutator function for example aggregate root.
        """

        # Handle "created" events by instantiating the aggregate class.
        if isinstance(event, AggregateCreated):
            aggregate = AggregateRoot(**event.__dict__)
            aggregate._version += 1
            return aggregate

        # Handle "entity created" events by adding a new entity to the aggregate's dict of entities.
        elif isinstance(event, EntityCreated):
            assert not aggregate.is_discarded
            entity = Example(entity_id=event.entity_id)
            aggregate._entities[entity.id] = entity
            aggregate._version += 1
            aggregate._last_modified_on = event.timestamp
            return aggregate

        # Handle "discarded" events by returning 'None'.
        elif isinstance(event, AggregateDiscarded):
            assert not aggregate.is_discarded
            aggregate._version += 1
            aggregate._is_discarded = True
            return None
        else:
            raise NotImplementedError(type(event))



Setup infrastructure using library classes.

.. code:: python

    from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemySettings, SQLAlchemyDatastore

    datastore = SQLAlchemyDatastore(
        settings=SQLAlchemySettings(uri='sqlite:///:memory:'),
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
    from eventsourcing.infrastructure.sqlalchemy.activerecords import SqlIntegerSequencedItem


    class ExampleDDDApplication(object):
        def __init__(self, datastore):
            self.event_store = EventStore(
                active_record_strategy=SQLAlchemyActiveRecordStrategy(
                    session=datastore.db_session,
                    active_record_class=SqlIntegerSequencedItem,
                ),
                sequenced_item_mapper=SequencedItemMapper(
                    sequence_id_attr_name='aggregate_id',
                    position_attr_name='aggregate_version',
                )
            )
            self.aggregate_repository = EventSourcedRepository(
                event_store=self.event_store,
                mutator=mutate_aggregate_event,
            )
            self.persistence_policy = PersistencePolicy(self.event_store, event_type=AggregateEvent)

        def create_example_aggregate(self):
            event = AggregateCreated(aggregate_id=uuid.uuid4())
            aggregate = mutate_aggregate_event(aggregate=None, event=event)
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
        assert aggregate.count_entities() == 0

        # Check the aggregate has zero entities.
        assert aggregate.count_entities() == 0

        # Ask the aggregate to create an entity within itself.
        aggregate.create_new_entity()

        # Check the aggregate has one entity.
        assert aggregate.count_entities() == 1

        # Check the aggregate in the repo still has zero entities.
        assert app.aggregate_repository[aggregate.id].count_entities() == 0

        # Call save().
        aggregate.save()

        # Check the aggregate in the repo now has one entity.
        assert app.aggregate_repository[aggregate.id].count_entities() == 1

        # Create two more entities within the aggregate.
        aggregate.create_new_entity()
        aggregate.create_new_entity()

        # Save both "entity created" events in one atomic transaction.
        aggregate.save()

        # Check the aggregate in the repo now has three entities.
        assert app.aggregate_repository[aggregate.id].count_entities() == 3

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
