===================
Stand-alone example
===================

In this section, an event sourced application is developed that has minimal
dependencies on the library.

A stand-alone domain model is developed without library classes, which shows
how event sourcing in Python can work. The stand-alone code examples here are
simplified versions of the library classes. Infrastructure classes from the
library are used explicitly to show the different components involved,
so you can understand how to make variations.

.. contents:: :local:


Domain
======

Let's start with the domain model. If the state of an event sourced application
is determined by a sequence of events, then we need to define some events.

Domain events
-------------

You may wish to use a technique such as "event storming" to identify or decide what
happens in your domain. In this example, for the sake of general familiarity let's
assume we have a domain in which things can be "created", "changed", and "discarded".
With that in mind, we can begin to write some domain event classes.

In the example below, there are three domain event classes: ``Created``,
``AttributeChanged``, and ``Discarded``. The common aspects of the domain
event classes have been pulled up to a layer supertype ``DomainEvent``.

.. code:: python

    class DomainEvent(object):
        """
        Supertype for domain event objects.
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
in your models, for example see
:class:`~eventsourcing.domain.model.events.CreatedEvent`,
:class:`~eventsourcing.domain.model.events.AttributeChangedEvent`, and
:class:`~eventsourcing.domain.model.events.DiscardedEvent`.


Publish-subscribe
-----------------

Since we are dealing with events, let's define a simple publish-subscribe mechanism for them.

.. code:: python

    subscribers = []

    def publish(events):
        for subscriber in subscribers:
            subscriber(events)


    def subscribe(subscriber):
        subscribers.append(subscriber)


    def unsubscribe(subscriber):
        subscribers.remove(subscriber)



Domain entity
-------------

Now, let's define a domain entity that publishes the event classes defined above.

The entity class ``Example`` below has an ID and a version number. It also
has a property ``foo`` with a "setter" method, and a method ``__discard__()`` to use
when the entity is no longer needed.

The entity methods follow a similar pattern. At some point, each
constructs an event that represents the result of the operation.
Then each uses a "mutator function" ``mutate()`` (see below) to
apply the event to the entity. Finally, each publishes the event
for the benefit of any subscribers, by using the function ``publish()``.

.. code:: python

    class Example(object):
        """
        Example domain entity.
        """
        def __init__(self, originator_id, originator_version=0, foo=''):
            self._id = originator_id
            self.___version__ = originator_version
            self._is_discarded = False
            self._foo = foo

        @property
        def id(self):
            return self._id

        @property
        def __version__(self):
            return self.___version__

        @property
        def foo(self):
            return self._foo

        @foo.setter
        def foo(self, value):
            assert not self._is_discarded

            # Construct an 'AttributeChanged' event object.
            event = AttributeChanged(
                originator_id=self.id,
                originator_version=self.__version__,
                name='foo',
                value=value,
            )

            # Apply the event to self.
            mutate(self, event)

            # Publish the event for others.
            publish([event])

        def discard(self):
            assert not self._is_discarded

            # Construct a 'Discarded' event object.
            event = Discarded(
                originator_id=self.id,
                originator_version=self.__version__
            )

            # Apply the event to self.
            mutate(self, event)

            # Publish the event for others.
            publish([event])


A factory can be used to create new "example" entities. The function
``create_new_example()`` below works in a similar way to the entity
methods, creating new entities by firstly constructing a ``Created``
event, then using the function ``mutate()`` (see below) to construct the entity
object, and finally publishing the event for others before returning
the new entity object to the caller.

.. code:: python

    import uuid

    def create_new_example(foo):
        """
        Factory for Example entities.
        """
        # Construct an entity ID.
        entity_id = uuid.uuid4()

        # Construct a 'Created' event object.
        event = Created(
            originator_id=entity_id,
            foo=foo
        )

        # Use the mutator function to construct the entity object.
        entity = mutate(None, event)

        # Publish the event for others.
        publish([event])

        # Return the new entity.
        return entity


The example entity class does not depend on the library. In particular, it doesn't
inherit from a "magical" entity base class that makes everything work. The example
here just publishes events that it has applied to itself. The library does however
contain domain entity classes that you can use to build your domain model, for
example the class :class:`~eventsourcing.domain.model.aggregate.AggregateRoot`.
The library classes are more developed than the examples here.


Mutator function
----------------

The mutator function ``mutate()`` below handles ``Created`` events by constructing
an object. It handles ``AttributeChanged`` events by setting an attribute value, and it
handles ``Discarded`` events by marking the entity as discarded. Each handler increases the
version of the entity, so that the version of the entity is always one plus the
the originator version of the last event that was applied.

When replaying a sequence of events, for example when reconstructing an entity from its
domain events, the mutator function is called many times in order to apply each event in
the sequence to an evolving initial state.

.. code:: python


    def mutate(entity, event):
        """
        Mutator function for Example entities.
        """
        # Handle "created" events by constructing the entity object.
        if isinstance(event, Created):
            entity = Example(**event.__dict__)
            entity.___version__ += 1
            return entity

        # Handle "value changed" events by setting the named value.
        elif isinstance(event, AttributeChanged):
            assert not entity._is_discarded
            setattr(entity, '_' + event.name, event.value)
            entity.___version__ += 1
            return entity

        # Handle "discarded" events by returning 'None'.
        elif isinstance(event, Discarded):
            assert not entity._is_discarded
            entity.___version__ += 1
            entity._is_discarded = True
            return None
        else:
            raise NotImplementedError(type(event))


For the sake of simplicity in this example, an if-else block is used to structure
the mutator function. The library has a function decorator
:func:`~eventsourcing.domain.model.decorators.mutator` that allows a default mutator
function to register handlers for different types of event, much like singledispatch.


Run the code
------------

Let's firstly subscribe to receive the events that will be published, so we can see what happened.

.. code:: python

    # A list of received events.
    received_events = []

    # Subscribe to receive published events.
    subscribe(lambda e: received_events.extend(e))


With this stand-alone code, we can create a new example entity object. We can update its property
``foo``, and we can discard the entity using the ``discard()`` method.

.. code:: python

    # Create a new entity using the factory.
    entity = create_new_example(foo='bar')

    # Check the entity has an ID.
    assert entity.id

    # Check the entity has a version number.
    assert entity.__version__ == 1

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
    assert entity.__version__ == 2

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

Please note, storing and replaying events to persist and to reconstruct
the state of an application is the primary capability of this
library. The domain and application and interface capabilities are offered
as a supplement to the infrastructural capabilities, and have been
added to the library partly as a way of shaping and validating the
infrastructure, partly to demonstrate how the core capabilities may
be applied, but also as a convenient way of reusing foundational code
so that attention can remain on the problem domain (framework).

To run the code in this section, please install the library with the
'sqlalchemy' option.

.. code::

    $ pip install eventsourcing[sqlalchemy]


Database table
--------------

Let's start by setting up a simple database table that can store sequences
of items. We can use SQLAlchemy directly to define a database table that
stores items in sequences, with a single identity for each sequence, and
with each item positioned in its sequence by an integer index number.

.. code:: python

    from sqlalchemy.ext.declarative.api import declarative_base
    from sqlalchemy.sql.schema import Column, Sequence, Index
    from sqlalchemy.sql.sqltypes import BigInteger, Integer, String, Text
    from sqlalchemy_utils import UUIDType

    Base = declarative_base()


    class IntegerSequencedRecord(Base):
        __tablename__ = 'integer_sequenced_items'

        id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)

        # Sequence ID (e.g. an entity or aggregate ID).
        sequence_id = Column(UUIDType(), nullable=False)

        # Position (index) of item in sequence.
        position = Column(BigInteger(), nullable=False)

        # Topic of the item (e.g. path to domain event class).
        topic = Column(String(255))

        # State of the item (serialized dict, possibly encrypted).
        state = Column(Text())

        __table_args__ = Index('index', 'sequence_id', 'position', unique=True),


The library has a class
:class:`~eventsourcing.infrastructure.sqlalchemy.models.IntegerSequencedRecord`
which is very similar to the above.

Next, create the database table. For convenience, the SQLAlchemy objects can be adapted
with the class
:class:`~eventsourcing.infrastructure.sqlalchemy.datastore.SQLAlchemyDatastore`, which
provides a simple interface for the two operations we require: ``setup_connection()``
and ``setup_tables()``.

.. code:: python

    from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemySettings, SQLAlchemyDatastore

    datastore = SQLAlchemyDatastore(
        base=Base,
        settings=SQLAlchemySettings(uri='sqlite:///:memory:'),
    )

    datastore.setup_connection()
    datastore.setup_table(IntegerSequencedRecord)


As you can see from the ``uri`` argument above, this example is using SQLite to manage
an in memory relational database. You can change ``uri`` to any valid connection string.
Here are some example connection strings: for an SQLite file; for a PostgreSQL database; and
for a MySQL database. See SQLAlchemy's create_engine() documentation for details. You may need
to install drivers for your database management system.

::

    sqlite:////tmp/mydatabase

    postgresql://scott:tiger@localhost:5432/mydatabase

    mysql://scott:tiger@hostname/dbname



Event store
-----------

To support different kinds of sequences in the domain model, and to allow for
different database schemas, the library has an event store class
:class:`~eventsourcing.infrastructure.eventstore.EventStore` that uses
a "sequenced item mapper" for mapping domain events to "sequenced items" - this
library's archetype persistence model for storing events. The sequenced item
mapper derives the values of sequenced item fields from the attributes of domain
events.

The event store then uses a record manager to persist the sequenced items
into a particular database management system. The record manager uses an
record class to manipulate records in a particular database table.

Hence you can use a different database table by substituting an alternative
record class. You can use a different database management system by substituting an
alternative record manager.

.. code:: python

    from eventsourcing.infrastructure.eventstore import EventStore
    from eventsourcing.infrastructure.sqlalchemy.manager import SQLAlchemyRecordManager
    from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper

    record_manager = SQLAlchemyRecordManager(
        session=datastore.session,
        record_class=IntegerSequencedRecord,
    )

    event_mapper = SequencedItemMapper(
        sequence_id_attr_name='originator_id',
        position_attr_name='originator_version'
    )

    event_store = EventStore(
        record_manager=record_manager,
        event_mapper=event_mapper
    )


In the code above, the ``sequence_id_attr_name`` value given to the sequenced item
mapper is the name of the domain events attribute that will be used as the ID
of the mapped sequenced item, The ``position_attr_name`` argument informs the
sequenced item mapper which event attribute should be used to position the item
in the sequence. The values ``originator_id`` and ``originator_version`` correspond
to attributes of the domain event classes we defined in the domain model section above.


Entity repository
-----------------

It is common to retrieve entities from a repository. An event sourced repository
for the ``example`` entity class can be constructed directly using library class
:class:`~eventsourcing.infrastructure.eventsourcedrepository.EventSourcedRepository`.

In this example, the repository is given an event store object. The repository is
also given the mutator function ``mutate()`` defined above.

.. code:: python

    from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository

    example_repository = EventSourcedRepository(
        event_store=event_store,
        mutator_func=mutate
    )


Run the code
------------

Now, let's firstly write the events we received earlier into the event store.

.. code:: python

    # Put each received event into the event store.
    event_store.store_events(received_events)

    # Check the events exist in the event store.
    stored_events = event_store.list_events(entity.id)
    assert len(stored_events) == 2, (received_events, stored_events)

The entity can now be retrieved from the repository, using its dictionary-like interface.

.. code:: python

    retrieved_entity = example_repository[entity.id]
    assert retrieved_entity.foo == 'baz'


Sequenced items
---------------

Remember that we can always get the sequenced items directly from the record manager.
A sequenced item is tuple containing a serialised representation of the domain event.
The library class :class:`~eventsourcing.infrastructure.sequenceditem.SequencedItem`
is a Python namedtuple with four fields: ``sequence_id``, ``position``, ``topic``,
and ``state``.

In this example, an event's ``originator_id`` attribute is mapped to the ``sequence_id``
field, and the event's ``originator_version`` attribute is mapped to the ``position``
field. The ``topic`` field of a sequenced item is used to identify the event class, and
the ``state`` field represents the state of the event (normally a JSON string).

.. code:: python

    sequenced_items = event_store.record_manager.list_items(entity.id)

    assert len(sequenced_items) == 2

    assert sequenced_items[0].sequence_id == entity.id
    assert sequenced_items[0].position == 0
    assert 'Created' in sequenced_items[0].topic
    assert b'bar' in sequenced_items[0].state

    assert sequenced_items[1].sequence_id == entity.id
    assert sequenced_items[1].position == 1
    assert 'AttributeChanged' in sequenced_items[1].topic
    assert b'baz' in sequenced_items[1].state


Application
===========

Although we can do everything at the module level, an application object brings
it all together. In the example below, the class ``ExampleApplication`` has an
event store, and an entity repository. The application also has a persistence policy.

Persistence policy
------------------

The persistence policy below subscribes to receive events whenever they are published. It
uses an event store to store events whenever they are received.

.. code:: python


    class PersistencePolicy(object):
        def __init__(self, event_store):
            self.event_store = event_store
            subscribe(self.store_events)

        def close(self):
            unsubscribe(self.store_events)

        def store_events(self, events):
            self.event_store.store_events(events)


A slightly more developed class :class:`~eventsourcing.application.policies.PersistencePolicy`
is included in the library.


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
                record_manager=SQLAlchemyRecordManager(
                    record_class=IntegerSequencedRecord,
                    session=session,
                ),
                event_mapper=SequencedItemMapper(
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
                mutator_func=mutate
            )

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.persistence_policy.close()

A more developed class :class:`~eventsourcing.example.application.ExampleApplication`
can be found in the library. It is used in later sections of this guide.


Run the code
============

With the application object, we can create more example entities
and expect they will be available immediately in the repository.

Please note, an entity that has been discarded by using its ``discard()`` method
cannot subsequently be retrieved from the repository using its ID. In particular,
the repository's dictionary-like interface will raise a Python ``KeyError``
exception instead of returning an entity.

.. code:: python

    with ExampleApplication(datastore.session) as app:

        # Create a new entity.
        example = create_new_example(foo='bar')

        # Read.
        assert example.id in app.example_repository
        assert app.example_repository[example.id].foo == 'bar'

        # Update.
        example.foo = 'baz'
        assert app.example_repository[example.id].foo == 'baz'

        # Delete.
        example.discard()
        assert example.id not in app.example_repository
