===================
Example application
===================

In this section, an application class is developed that has minimal
dependencies on the library.

A stand-alone domain model is developed without library classes, which shows
how event sourcing in Python can work. The stand-alone examples here are
simplified versions of the library classes.

All the infrastructure is declared explicitly to show the components that are
involved.


Domain
======

Let's start with the domain model. Since the state of an event sourced application
is determined by a sequence of events, so we need to define some events.

Domain events
-------------

You may wish to use a technique such as "event storming" to identify or decide what
happens in your domain. In this example, for the sake of general familiarity, let's
assume we have a domain in which things can be "created", "changed", and "discarded".
With that in mind, we can begin to write some domain event classes.

In the example below, there are three domain event classes: ``Created``,
``AttributeChanged``, and ``Discarded``. The common attributes of the domain
event classes have been pulled up to a layer supertype ``DomainEvent``.

.. code:: python

    import time


    class DomainEvent(object):
        """
        Layer supertype.
        """
        def __init__(self, originator_id, originator_version, **kwargs):
            self.originator_id = originator_id
            self.originator_version = originator_version
            self.__dict__.update(kwargs)


    class Created(DomainEvent):
        """
        Published when an entity is created.
        """
        def __init__(self, **kwargs):
            super(Created, self).__init__(originator_version=0, **kwargs)


    class AttributeChanged(DomainEvent):
        """
        Published when an attribute value is changed.
        """
        def __init__(self, name, value, **kwargs):
            super(AttributeChanged, self).__init__(**kwargs)
            self.name = name
            self.value = value


    class Discarded(DomainEvent):
        """
        Published when an entity is discarded.
        """


Please note, the domain event classes above do not depend on the library. The library does
however contain a collection of different kinds of domain event classes that you can use
in your models, for example see ``Created``, ``AttributeChanged``, ``Discarded`` in
``eventsourcing.domain.model.events``, their supertype ``DomainEvent``, and the inner
classes on various entity classes. The library classes are more developed than the examples here.

Domain entity
-------------

Now, let's define a domain entity that publishes the event classes defined above.

The ``Example`` entity class below has an entity ID, and a version number. It also
has an attribute ``foo``, and a method ``discard()`` to use when the entity is
discarded.

.. code:: python

    import uuid

    from eventsourcing.domain.model.events import publish


    class Example(object):
        """
        Example domain entity.
        """
        def __init__(self, originator_id, originator_version=0, foo=''):
            self._id = originator_id
            self._version = originator_version
            self._is_discarded = False
            self._foo = foo

        @property
        def id(self):
            return self._id

        @property
        def version(self):
            return self._version

        @property
        def foo(self):
            return self._foo

        @foo.setter
        def foo(self, value):
            assert not self._is_discarded

            # Instantiate a domain event.
            event = AttributeChanged(
                originator_id=self.id,
                originator_version=self.version,
                name='foo',
                value=value,
            )

            # Apply the event to self.
            mutate(self, event)

            # Publish the event for others.
            publish(event)

        def discard(self):
            assert not self._is_discarded

            # Instantiate a domain event.
            event = Discarded(
                originator_id=self.id,
                originator_version=self.version
            )

            # Apply the event to self.
            mutate(self, event)

            # Publish the event for others.
            publish(event)


The entity methods follow a similar pattern. Each constructs an event that represents the result
of the operation. Each uses a "mutator function" function ``mutate()`` to apply the event
to the entity. Each publishes the event for the benefit of any subscribers.

The factory ``create_new_example()`` below, which works in the same way, can be used to create
new entities.

.. code:: python

    def create_new_example(foo):
        """
        Factory for Example entities.
        """
        # Create an entity ID.
        entity_id = uuid.uuid4()

        # Instantiate a domain event.
        event = Created(
            originator_id=entity_id,
            foo=foo
        )

        # Mutate the event to construct the entity.
        entity = mutate(None, event)

        # Publish the event for others.
        publish(event=event)

        # Return the new entity.
        return entity


When replaying a sequence of events, for example when reconstituting an entity from its
domain events, the mutator function is called several times in order to apply every event
to an evolving initial state. For the sake of simplicity in this example, we'll use an
if-else block that can handle the three types of events published by the example entity.

.. code:: python


    def mutate(entity, event):
        """
        Mutator for Example entities.
        """
        # Handle "created" events by instantiating the entity class.
        if isinstance(event, Created):
            entity = Example(**event.__dict__)
            entity._version += 1
            return entity

        # Handle "value changed" events by setting the named value.
        elif isinstance(event, AttributeChanged):
            assert not entity._is_discarded
            setattr(entity, '_' + event.name, event.value)
            entity._version += 1
            return entity

        # Handle "discarded" events by returning 'None'.
        elif isinstance(event, Discarded):
            assert not entity._is_discarded
            entity._version += 1
            entity._is_discarded = True
            return None
        else:
            raise NotImplementedError(type(event))


The example entity class does not depend on the library, except for the ``publish()`` function.
In particular, it doesn't inherit from a "magical" entity base class that makes everything work.
The example here just publishes events that it has applied to itself. The library does however
contain domain entity classes that you can use to build your domain model, for example the
``AggregateRoot`` class in ``eventsourcing.domain.model.aggregate``. The library classes are
more developed than the examples here.


Run the code
------------

Let's firstly subscribe to receive the events that will be published, so we can see what happened.

.. code:: python

    from eventsourcing.domain.model.events import subscribe

    # A list of received events.
    received_events = []

    # Subscribe to receive published events.
    subscribe(lambda e: received_events.append(e))


With this stand-alone code, we can create a new example entity object. We can update its property
``foo``, and we can discard the entity using the ``discard()`` method.

.. code:: python

    # Create a new entity using the factory.
    entity = create_new_example(foo='bar')

    # Check the entity has an ID.
    assert entity.id

    # Check the entity has a version number.
    assert entity.version == 1

    # Check the received events.
    assert len(received_events) == 1, received_events
    assert isinstance(received_events[0], Created)
    assert received_events[0].originator_id == entity.id
    assert received_events[0].originator_version == 0
    assert received_events[0].foo == 'bar'

    # Check the value of property 'foo'.
    assert entity.foo == 'bar'

    # Update property 'foo'.
    entity.foo = 'baz'

    # Check the new value of 'foo'.
    assert entity.foo == 'baz'

    # Check the version number has increased.
    assert entity.version == 2

    # Check the received events.
    assert len(received_events) == 2, received_events
    assert isinstance(received_events[1], AttributeChanged)
    assert received_events[1].originator_version == 1
    assert received_events[1].name == 'foo'
    assert received_events[1].value == 'baz'


Infrastructure
==============

Since the application state is determined by a sequence of events, the
application must somehow be able both to persist the events, and then
recover the entities.


Database table
--------------

Let's start by setting up a simple database table that can store sequences
of items. We can use SQLAlchemy to define a database table that stores
items in sequences, with a single identity for each sequence, and with
each item positioned in its sequenced by an integer index number.

.. code:: python

    from sqlalchemy.ext.declarative.api import declarative_base
    from sqlalchemy.sql.schema import Column, Sequence, UniqueConstraint
    from sqlalchemy.sql.sqltypes import BigInteger, Integer, String, Text
    from sqlalchemy_utils import UUIDType

    ActiveRecord = declarative_base()


    class SequencedItemRecord(ActiveRecord):
        __tablename__ = 'sequenced_items'

        id = Column(Integer(), Sequence('integer_sequened_item_id_seq'), primary_key=True)

        # Sequence ID (e.g. an entity or aggregate ID).
        sequence_id = Column(UUIDType(), index=True)

        # Position (index) of item in sequence.
        position = Column(BigInteger(), index=True)

        # Topic of the item (e.g. path to domain event class).
        topic = Column(String(255))

        # State of the item (serialized dict, possibly encrypted).
        data = Column(Text())

        # Unique constraint.
        __table_args__ = UniqueConstraint('sequence_id', 'position',
                                          name='integer_sequenced_item_uc'),


Now create the database table. For convenience, the SQLAlchemy objects can be adapted
with the ``SQLAlchemyDatastore`` class, which provides a simple interface for the
two operations we require: ``setup_connection()`` and ``setup_tables()``.

.. code:: python

    from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemySettings, SQLAlchemyDatastore

    datastore = SQLAlchemyDatastore(
        base=ActiveRecord,
        settings=SQLAlchemySettings(uri='sqlite:///:memory:'),
        tables=(SequencedItemRecord,),
    )

    datastore.setup_connection()
    datastore.setup_tables()


As you can see from the ``uri`` argument above, this example is using SQLite to manage
an in memory relational database. You can change ``uri`` to any valid connection string.
Here are some example connection strings: for an SQLite file; for a PostgreSQL database; and
for a MySQL database. See SQLAlchemy's create_engine() documentation for details.

::

    sqlite:////tmp/mydatabase

    postgresql://scott:tiger@localhost:5432/mydatabase

    mysql://scott:tiger@hostname/dbname


Event store
-----------

To support different kinds of sequences in the domain model, and to allow for
different database schemas, the library has an event store that uses
a "sequenced item mapper" for mapping domain events to "sequenced items" - this
library's archetype persistence model for storing events. The sequenced item
mapper derives the values of sequenced item fields from the attributes of domain
events.

The event store then uses an "active record strategy" to persist the sequenced items
into a particular database management system. The active record strategy uses an
active record class to manipulate records in a particular database table.

Hence you can use a different database table by substituting an alternative active
record class. You can use a different database management system by substituting an
alternative active record strategy. The persistence model can also be changed
by substituting an alternative sequenced item type.

.. code:: python

    from eventsourcing.infrastructure.eventstore import EventStore
    from eventsourcing.infrastructure.sqlalchemy.activerecords import SQLAlchemyActiveRecordStrategy
    from eventsourcing.infrastructure.sequenceditem import SequencedItem
    from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper

    active_record_strategy = SQLAlchemyActiveRecordStrategy(
        session=datastore.session,
        active_record_class=SequencedItemRecord,
        sequenced_item_class=SequencedItem
    )

    sequenced_item_mapper = SequencedItemMapper(
        sequenced_item_class=SequencedItem,
        sequence_id_attr_name='originator_id',
        position_attr_name='originator_version'
    )

    event_store = EventStore(
        active_record_strategy=active_record_strategy,
        sequenced_item_mapper=sequenced_item_mapper
    )


In the code above, the ``sequence_id_attr_name`` value given to the sequenced item
mapper is the name of the domain events attribute that will be used as the ID
of the mapped sequenced item, The ``position_attr_name`` argument informs the
sequenced item mapper which event attribute should be used to position the item
in the sequence. The values ``originator_id`` and ``originator_version`` correspond
to attributes of the domain event classes we defined in the domain model section above.


Entity repository
-----------------

It is common to retrieve entities from a repository. An event sourced
repository for the ``example`` entity class can be constructed directly using the
``EventSourcedRepository`` library class. The repository is given the mutator function
``mutate()`` and the event store.


.. code:: python

    from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository

    example_repository = EventSourcedRepository(
        event_store=event_store,
        mutator=mutate
    )


Run the code
------------

Now, let's firstly write the events we received earlier into the event store.

.. code:: python

    # Put each received event into the event store.
    for event in received_events:
        event_store.append(event)

    # Check the events exist in the event store.
    stored_events = event_store.get_domain_events(entity.id)
    assert len(stored_events) == 2, (received_events, stored_events)

The entity can now be retrieved from the repository, using its dictionary-like interface.

.. code:: python

    retrieved_entity = example_repository[entity.id]
    assert retrieved_entity.foo == 'baz'


Sequenced items
---------------

Remember that we can always get the sequenced items directly from the active record
strategy. A sequenced item is tuple containing a serialised representation of the
domain event. In the library, a ``SequencedItem`` is a Python tuple with four fields:
``sequence_id``, ``position``, ``topic``, and ``data``. In this example, an event's
``originator_id`` attribute is mapped to the ``sequence_id`` field, and the event's
``originator_version`` attribute is mapped to the ``position`` field. The ``topic``
field of a sequenced item is used to identify the event class, and the ``data`` field
represents the state of the event (a JSON string).

.. code:: python

    sequenced_items = event_store.active_record_strategy.get_items(entity.id)

    assert len(sequenced_items) == 2

    assert sequenced_items[0].sequence_id == entity.id
    assert sequenced_items[0].position == 0
    assert 'Created' in sequenced_items[0].topic
    assert 'bar' in sequenced_items[0].data

    assert sequenced_items[1].sequence_id == entity.id
    assert sequenced_items[1].position == 1
    assert 'AttributeChanged' in sequenced_items[1].topic
    assert 'baz' in sequenced_items[1].data

Similar to the support for storing events in SQLAlchemy, there
are classes in the library for Cassandra. Support for other
databases is forthcoming.


Application
===========

Although we can do everything at the module level, an application object brings
it all together. In the example below, the class ``ExampleApplication`` has an
event store, and an entity repository. The application also has a persistence policy.

Persistence Policy
------------------

The persistence policy subscribes to receive events whenever they are published. It
uses an event store to store events whenever they are received.


.. code:: python

    from eventsourcing.domain.model.events import subscribe, unsubscribe


    class PersistencePolicy(object):
        def __init__(self, event_store):
            self.event_store = event_store
            subscribe(self.store_event, self.is_event)

        def is_event(self, event):
            return isinstance(event, DomainEvent)

        def store_event(self, event):
            self.event_store.append(event)

        def close(self):
            unsubscribe(self.store_event, self.is_event)



Application object
------------------

As a convenience, it is useful to make the application function as a Python
context manager, so that the application can close the persistence policy,
and unsubscribe from receiving further domain events.

.. code:: python

    class ExampleApplication(object):
        def __init__(self, session):
            # Construct event store.
            self.event_store = EventStore(
                active_record_strategy=SQLAlchemyActiveRecordStrategy(
                    session=session,
                    active_record_class=SequencedItemRecord,
                    sequenced_item_class=SequencedItem
                ),
                sequenced_item_mapper=SequencedItemMapper(
                    sequenced_item_class=SequencedItem,
                    sequence_id_attr_name='originator_id',
                    position_attr_name='originator_version'
                )
            )
            # Construct persistence policy.
            self.persistence_policy = PersistencePolicy(
                event_store=self.event_store
            )
            # Construct example repository.
            self.example_repository = EventSourcedRepository(
                event_store=self.event_store,
                mutator=mutate
            )

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.persistence_policy.close()


Run the code
============

After instantiating the application, the entity above is available.

.. code:: python

    with ExampleApplication(datastore.session) as app:

        # Read the entity from events published above.
        assert entity.id in app.example_repository
        assert app.example_repository[entity.id].foo == 'baz'


With the application object, we can create more example entities
and expect they will be available immediately in the repository.

Please note, an entity that has been discarded by using its ``discard()`` method
cannot subsequently be retrieved from the repository using its ID. In particular,
the repository's dictionary-like interface will raise a Python ``KeyError``
exception instead of returning an entity.

    with ExampleApplication(datastore.session) as app:

        # Create a new entity.
        entity2 = create_new_example(foo='bar')

        # Read.
        assert entity2.id in app.example_repository
        assert app.example_repository[entity2.id].foo == 'bar'

        # Update.
        entity2.foo = 'baz'
        assert app.example_repository[entity2.id].foo == 'baz'

        # Delete.
        entity2.discard()
        assert entity2.id not in app.example_repository



Congratulations. You have created yourself an event sourced application.

A more developed ``ExampleApplication`` class can be found in the library
module ``eventsourcing.example.application``. It is used in later sections
of this guide.
