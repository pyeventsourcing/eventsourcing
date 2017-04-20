===================
Example Application
===================


This example follows the layered architecture: application, domain, and
infrastructure. Let's start with the domain model.

Domain model
============

The state of an event sourced application is determined by a
sequence of events, so we need to define some events. Also, events
result from commands, so we also need to define an entity.


Domain events
-------------

For the sake of simplicity in this example, let's assume things in our
domain can be "created", "changed", and "discarded". With that in mind,
let's define some domain event classes.

In the example below, the common attributes of a domain event, such as the entity ID
and version, and the timestamp of the event, have been pulled up to a layer supertype
called ``DomainEvent``.

.. code:: python

    import time


    class DomainEvent(object):
        """
        Layer supertype.
        """
        def __init__(self, entity_id, entity_version, timestamp=None, **kwargs):
            self.entity_id = entity_id
            self.entity_version = entity_version
            self.timestamp = timestamp or time.time()
            self.__dict__.update(kwargs)


    class Created(DomainEvent):
        """
        Published when an entity is created.
        """
        def __init__(self, **kwargs):
            super(Created, self).__init__(entity_version=0, **kwargs)


    class ValueChanged(DomainEvent):
        """
        Published when an attribute value is changed.
        """
        def __init__(self, name, value, **kwargs):
            super(ValueChanged, self).__init__(**kwargs)
            self.name = name
            self.value = value


    class Discarded(DomainEvent):
        """
        Published when an entity is discarded.
        """


Please note, the domain event classes above do not depend on the library. The library does
however contain a collection of different kinds of domain event classes that you can use
in your models, for example see ``AggregateEvent``. The domain event classes in the
library are slightly more sophisticated than the code in this example.


Domain entity
-------------

Now, let's use the event classes above to define a domain entity.

The ``Example`` entity class below has an entity ID, a version number, and a
timestamp. It also has a property ``foo``, and a ``discard()`` method to use
when the entity is discarded. The factory method ``create_new_example()`` can
be used to create new entities.

All the methods follow a similar pattern. Each constructs an event that represents the result
of the operation. Each uses a "mutator function" function ``mutate()`` to apply the event
to the entity. Then each publishes the event for the benefit of any subscribers.

When replaying a sequence of events, for example when reconsistuting an entity from its
domain events, the mutator function is also successively to apply every event to an evolving
initial state. For the sake of simplicity in this example, we'll use an if-else block
that can handle the three types of events defined above.

.. code:: python

    import uuid

    from eventsourcing.domain.model.events import publish


    class Example(object):
        """
        Example domain entity.
        """
        def __init__(self, entity_id, entity_version=0, foo='', timestamp=None):
            self._id = entity_id
            self._version = entity_version
            self._is_discarded = False
            self._created_on = timestamp
            self._last_modified_on = timestamp
            self._foo = foo

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

        @property
        def foo(self):
            return self._foo

        @foo.setter
        def foo(self, value):
            assert not self._is_discarded
            # Instantiate a domain event.
            event = ValueChanged(
                entity_id=self.id,
                entity_version=self.version,
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
            event = Discarded(entity_id=self.id, entity_version=self.version)
            # Apply the event to self.
            mutate(self, event)
            # Publish the event for others.
            publish(event)


    def create_new_example(foo):
        """
        Factory for Example entities.
        """
        # Create an entity ID.
        entity_id = uuid.uuid4()
        # Instantiate a domain event.
        event = Created(entity_id=entity_id, foo=foo)
        # Mutate the event to construct the entity.
        entity = mutate(None, event)
        # Publish the event for others.
        publish(event=event)
        # Return the new entity.
        return entity


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
        elif isinstance(event, ValueChanged):
            assert not entity.is_discarded
            setattr(entity, '_' + event.name, event.value)
            entity._version += 1
            entity._last_modified_on = event.timestamp
            return entity
        # Handle "discarded" events by returning 'None'.
        elif isinstance(event, Discarded):
            assert not entity.is_discarded
            entity._version += 1
            entity._is_discarded = True
            return None
        else:
            raise NotImplementedError(type(event))


The example entity class does not depend on the library, except for the ``publish()`` function.
In particular, it doesn't inherit from a "magical" entity base class. It just publishes events that it has
applied to itself. The library does however contain domain entity classes that you can use to build your
domain model. For example see the ``TimestampedVersionedEntity`` class, which is also a timestamped,
versioned entity. The library classes are slightly more refined than the code in this example.


Run the code
------------

With this stand-alone code, we can create a new example entity object. We can update its property
``foo``, and we can discard the entity using the ``discard()`` method. Let's firstly subscribe to
receive the events that will be published, so we can see what happened.

.. code:: python

    from eventsourcing.domain.model.events import subscribe

    # A list of received events.
    received_events = []

    # Subscribe to receive published events.
    subscribe(lambda e: received_events.append(e))

    # Create a new entity using the factory.
    entity = create_new_example(foo='bar1')

    # Check the entity has an ID.
    assert entity.id

    # Check the entity has a version number.
    assert entity.version == 1

    # Check the received events.
    assert len(received_events) == 1, received_events
    assert isinstance(received_events[0], Created)
    assert received_events[0].entity_id == entity.id
    assert received_events[0].entity_version == 0
    assert received_events[0].foo == 'bar1'

    # Check the value of property 'foo'.
    assert entity.foo == 'bar1'

    # Update property 'foo'.
    entity.foo = 'bar2'

    # Check the new value of 'foo'.
    assert entity.foo == 'bar2'

    # Check the version number has increased.
    assert entity.version == 2

    # Check the received events.
    assert len(received_events) == 2, received_events
    assert isinstance(received_events[1], ValueChanged)
    assert received_events[1].entity_version == 1
    assert received_events[1].name == 'foo'
    assert received_events[1].value == 'bar2'



Infrastructure
==============

Since the application state is determined by a sequence of events, the events of the
application must somehow be stored, and the entities somehow retrieved.

Database table
--------------

Let's start by setting up a simple database. We can use SQLAlchemy to define a
database table that stores integer-sequenced items.

.. code:: python

    from sqlalchemy.ext.declarative.api import declarative_base
    from sqlalchemy.sql.schema import Column, Sequence, UniqueConstraint
    from sqlalchemy.sql.sqltypes import BigInteger, Integer, String, Text
    from sqlalchemy_utils import UUIDType

    Base = declarative_base()


    class SequencedItemTable(Base):
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


Now create the database table. The SQLAlchemy objects can be adapted with a ``Datastore`` from the
library, which provides a common interface for the operations ``setup_connection()``
and ``setup_tables()``.

.. code:: python

    from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemySettings, SQLAlchemyDatastore

    datastore = SQLAlchemyDatastore(
        base=Base,
        settings=SQLAlchemySettings(uri='sqlite:///:memory:'),
    )

    datastore.setup_connection()
    datastore.setup_tables()

This example uses an SQLite in memory relational database. You can
change ``uri`` to any valid connection string. Here are some example
connection strings: for an SQLite file; for a PostgreSQL database; and
for a MySQL database. See SQLAlchemy's create_engine() documentation for details.

::

    sqlite:////tmp/mydatabase

    postgresql://scott:tiger@localhost:5432/mydatabase

    mysql://scott:tiger@hostname/dbname


Event store
-----------

To support different kinds of sequences, and to allow for different schemas
for storing events, the event store has been factored to use a "sequenced
item mapper" to map domain events to sequenced items, and an "active record
strategy" to write sequenced items into a database table. The details
have been made explicit so they can be easily replaced.

The sequenced item mapper derives the values of sequenced item fields from
the attributes of domain events. The active record strategy uses an active
record class to access rows in a database table. Hence you you could vary the
field types and indexes used in the database table by passing in an alternative
active record class. You can use alternative field names in the database
table by using an alternative sequenced item class, along with a suitable active
record class, reusing the sequenced item mapper and the active record strategy.

You can extend or replace the persistence model by extending the sequenced item
mapper and sequenced item class, and using them along with a suitable active
record class. A new database system or service can be adapted with a new active
record strategy.

In the code below, the args ``sequence_id_attr_name`` and ``position_attr_name``
inform the sequenced item mapper which domain event attributes should be used for the
sequence ID and position fields of a sequenced item. It isn't necessary to
provide the ``sequence_id_attr_name`` arg, if the name of the domain event
attribute holding the sequence ID value is equal to the name of the first field
of the sequenced item class - for example if both are called 'aggregate_id'. Similarly,
it isn't necessary to provide a value for the ``position_attr_name`` arg, if the name
of the domain event attribute which indicates the position of the event in a sequence
is equal to the name of the second field of the sequence item class - for example if both
are called 'aggregate_version' (see below).


.. code:: python

    from eventsourcing.infrastructure.eventstore import EventStore
    from eventsourcing.infrastructure.sqlalchemy.activerecords import SQLAlchemyActiveRecordStrategy
    from eventsourcing.infrastructure.sequenceditem import SequencedItem
    from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper

    active_record_strategy = SQLAlchemyActiveRecordStrategy(
        datastore=datastore,
        active_record_class=SequencedItemTable,
        sequenced_item_class=SequencedItem
    )

    sequenced_item_mapper = SequencedItemMapper(
        sequenced_item_class=SequencedItem,
        sequence_id_attr_name='entity_id',
        position_attr_name='entity_version'
    )

    event_store = EventStore(
        active_record_strategy=active_record_strategy,
        sequenced_item_mapper=sequenced_item_mapper
    )

Entity repository
-----------------

It is common pattern to retrieve entities from a repository. An event sourced
repository for the ``example`` entity class can be constructed directly using the
``EventSourcedRepository`` library class. The repository is given the mutator function
``mutate()`` and the event store, so that it can make an event player.


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
    assert retrieved_entity.foo == 'bar2'

Remember that we can always get the sequenced items directly from the active record
strategy. A sequenced item is tuple containing a serialised representation of the domain event. In the library, a
``SequencedItem`` is a Python tuple with four fields: ``sequence_id``, ``position``,
``topic``, and ``data``. By default, an event's ``entity_id`` attribute is mapped to the ``sequence_id`` field,
and the event's ``entity_version`` attribute is mapped to the ``position`` field. The ``topic`` field of a
sequenced item is used to identify the event class, and the ``data`` field represents the state of the event (a
JSON string).

.. code:: python

    sequenced_items = event_store.active_record_strategy.get_items(entity.id)

    assert len(sequenced_items) == 2

    assert sequenced_items[0].sequence_id == entity.id
    assert sequenced_items[0].position == 0
    assert 'Created' in sequenced_items[0].topic
    assert 'bar1' in sequenced_items[0].data

    assert sequenced_items[1].sequence_id == entity.id
    assert sequenced_items[1].position == 1
    assert 'ValueChanged' in sequenced_items[1].topic
    assert 'bar2' in sequenced_items[1].data

Similar to the support for storing events in SQLAlchemy, there
are classes in the library for Cassandra. Support for other
databases is forthcoming.


Application
===========

Although we can do everything at the module level, an application object brings
everything together. In the example below, the application has an event store,
and an entity repository.

Most importantly, the application has a persistence policy. The persistence
policy firstly subscribes to receive events when they are published, and it
uses the event store to store all the events that it receives.

As a convenience, it is useful to make the application function as a Python
context manager, so that the application can close the persistence policy,
unsubscribing itself from receiving further domain events.

.. code:: python

    from eventsourcing.application.policies import PersistencePolicy

    class Application(object):

        def __init__(self, datastore):
            self.event_store = EventStore(
                active_record_strategy=SQLAlchemyActiveRecordStrategy(
                    datastore=datastore,
                    active_record_class=SequencedItemTable,
                    sequenced_item_class=SequencedItem,
                ),
                sequenced_item_mapper=SequencedItemMapper(
                    sequenced_item_class=SequencedItem,
                    sequence_id_attr_name='entity_id',
                    position_attr_name='entity_version',
                )
            )
            self.example_repository = EventSourcedRepository(
                event_store=self.event_store,
                mutator=mutate,
            )
            self.persistence_policy = PersistencePolicy(self.event_store, event_type=DomainEvent)

        def create_example(self, foo):
            return create_new_example(foo=foo)

        def close(self):
            self.persistence_policy.close()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.close()

After instantiating the application, we can create more example entities
and expect they will be available in the repository immediately.

Please note, a discarded entity can not be retrieved from the repository.
The repository's dictionary-like interface will raise a Python ``KeyError``
exception instead of returning an entity.

.. code:: python

    with Application(datastore) as app:

        entity = app.create_example(foo='bar1')

        assert entity.id in app.example_repository

        assert app.example_repository[entity.id].foo == 'bar1'

        entity.foo = 'bar2'

        assert app.example_repository[entity.id].foo == 'bar2'

        # Discard the entity.
        entity.discard()
        assert entity.id not in app.example_repository

        try:
            app.example_repository[entity.id]
        except KeyError:
            pass
        else:
            raise Exception('KeyError was not raised')


Congratulations. You have created yourself an event sourced application.

A slightly more developed example application can be found in the library
module ``eventsourcing.example.application``.
