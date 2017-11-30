============
Applications
============

The application layer combines objects from the domain and
infrastructure layers.

Repositories and policies
=========================

An application object can have repositories, so that aggregates
can be retrieved by ID using a dictionary-like interface.
In general, aggregates implement commands that publish events.

An application object can also have policies. In general, policies receive
events and execute commands.


Application services
====================

An application object can have methods ("application services")
which provide a relatively simple interface for clients operations,
hiding the complexity and usage of the application's domain and
infrastructure layers.

Application services can be developed outside-in, with a
test- or behaviour-driven development approach. A test suite can be imagined as an
interface that uses the application. Interfaces are outside the scope of
the application layer.


Example application
===================

The library provides a simple application class, called ``SimpleApplication``.
The example below shows a simple event sourced application object class
that extends this class, by constructing a repository when the application object is
constructed, and by defining a factory method that can create new aggregates
of the ``CustomAggregate`` type.

.. code:: python

    from uuid import uuid4

    from eventsourcing.application.simple import SimpleApplication

    class MyApplication(SimpleApplication):
        def __init__(self, event_store):
            super(MyApplication, self).__init__(event_store)

            # Construct an event sourced repository.
            self.repository = self.construct_repository(CustomAggregate)

        def create_aggregate(self, a):
            return CustomAggregate.create(a=1)


Aggregate
---------

The example application code above depends on one entity class called ``CustomAggregate``,
defined below. It extends the library's ``AggregateRoot`` entity with event sourced
attribute ``a``.

.. code:: python

    from eventsourcing.domain.model.aggregate import AggregateRoot
    from eventsourcing.domain.model.decorators import attribute


    class CustomAggregate(AggregateRoot):
        def __init__(self, a, **kwargs):
            super(CustomAggregate, self).__init__(**kwargs)
            self._a = a

        @attribute
        def a(self):
            """
            Event sourced attribute 'a'.
            """


For more sophisticated domain models, please read
more about the :doc:`domain model layer </topics/domainmodel>`.


Repository
----------

The application has an event sourced repository for ``CustomAggregate`` instances.
It is constructed using the method ``construct_repository()`` of ``SimpleApplication``.

That method uses the library class ``EventSourcedRepository``, which uses an event store
to get domain events for an aggregate. It also uses a mutator function from the aggregate
class, which it uses to reconstruct an aggregate from its events. A simple application
would normally have one such repository for each type of aggregate in the application's
domain model.


Policy
------

The ``SimpleApplication`` class has a persistence policy. It uses the library class
``PersistencePolicy``. The persistence policy appends domain events to its event
store whenever they are published.


Aggregate factory
-----------------

The application above has an application service called ``create_aggregate()`` which can be used
to create new ``CustomAggregate`` instances. To create such an aggregate using this factory
method, a value for ``a`` must be provided.


Database
--------

The library classes ``SQLAlchemyDatastore`` and ``SQLAlchemySettings`` can be
used to setup a database.

.. code:: python

    from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemyDatastore, SQLAlchemySettings
    from eventsourcing.infrastructure.sqlalchemy.activerecords import StoredEventRecord

    # Define database settings.
    settings = SQLAlchemySettings(uri='sqlite:///:memory:')

    # Setup connection to database.
    datastore = SQLAlchemyDatastore(settings=settings)
    datastore.setup_connection()


Event store
-----------

An event store can be constructed that uses SQLAlchemy, using library
function ``construct_sqlalchemy_eventstore()``, and the database ``session``.

.. code:: python

    from eventsourcing.infrastructure.sqlalchemy.factory import construct_sqlalchemy_eventstore

    # Construct event store.
    event_store = construct_sqlalchemy_eventstore(datastore.session)

    # Setup table in database.
    active_record_class = event_store.active_record_strategy.active_record_class
    datastore.setup_table(active_record_class)


For alternative infrastructure, please read more about
the :doc:`infrastructure layer </topics/infrastructure>`.


Run the code
------------

The application can be constructed with the event store.

.. code:: python

    # Construct application object.
    app = MyApplication(event_store)


Now, a new aggregate instance can be created with the application service ``create_aggregate()``.

.. code:: python

    # Create aggregate using application service.
    aggregate = app.create_aggregate(a=1)

    # Don't forget to save!
    aggregate.save()


The aggregate now exists in the repository. An existing aggregate can
be retrieved by ID using the repository's dictionary-like interface.

.. code:: python

    # Aggregate is in the repository.
    assert aggregate.id in app.repository

    # Get aggregate using dictionary-like interface.
    aggregate = app.repository[aggregate.id]

    assert aggregate.a == 1


Changes to the aggregate's attribute ``a`` are visible in
the repository, but only after the aggregate has been saved.

.. code:: python

    aggregate.a = 2
    aggregate.a = 3

    # Don't forget to save!
    aggregate.save()

    # Retrieve again from repository.
    aggregate = app.repository[aggregate.id]

    # Check attribute has new value.
    assert aggregate.a == 3


The aggregate can be discarded. After being saved, a discarded
aggregate will no longer be available in the repository.

.. code:: python

    # Discard the aggregate.
    aggregate.discard()

    # Don't forget to save!
    aggregate.save()

    # Check discarded aggregate no longer exists in repository.
    assert aggregate.id not in app.repository


Attempts to retrieve an aggregate that does not
exist will cause a ``KeyError`` to be raised.

.. code:: python

    # Fail to get aggregate from dictionary-like interface.
    try:
        app.repository[aggregate.id]
    except KeyError:
        pass
    else:
        raise Exception("Shouldn't get here")


Application events
------------------

It is always possible to get the domain events for an aggregate, using the application's event store method
``get_domain_events()``.

.. code:: python

    events = app.event_store.get_domain_events(originator_id=aggregate.id)
    assert len(events) == 4

    assert events[0].originator_id == aggregate.id
    assert isinstance(events[0], CustomAggregate.Created)
    assert events[0].a == 1

    assert events[1].originator_id == aggregate.id
    assert isinstance(events[1], CustomAggregate.AttributeChanged)
    assert events[1].name == '_a'
    assert events[1].value == 2

    assert events[2].originator_id == aggregate.id
    assert isinstance(events[2], CustomAggregate.AttributeChanged)
    assert events[2].name == '_a'
    assert events[2].value == 3

    assert events[3].originator_id == aggregate.id
    assert isinstance(events[3], CustomAggregate.Discarded)


Sequenced items
---------------

It is also possible to get the sequenced item namedtuples for an aggregate, using the application's event store's
active record strategy method ``get_items()``.

.. code:: python

    items = app.event_store.active_record_strategy.get_items(aggregate.id)
    assert len(items) == 4

    assert items[0].originator_id == aggregate.id
    assert items[0].event_type == 'eventsourcing.domain.model.aggregate#AggregateRoot.Created'
    assert '"a":1' in items[0].state
    assert '"timestamp":' in items[0].state

    assert items[1].originator_id == aggregate.id
    assert items[1].event_type == 'eventsourcing.domain.model.aggregate#AggregateRoot.AttributeChanged'
    assert '"name":"_a"' in items[1].state
    assert '"timestamp":' in items[1].state

    assert items[2].originator_id == aggregate.id
    assert items[2].event_type == 'eventsourcing.domain.model.aggregate#AggregateRoot.AttributeChanged'
    assert '"name":"_a"' in items[2].state
    assert '"timestamp":' in items[2].state

    assert items[3].originator_id == aggregate.id
    assert items[3].event_type == 'eventsourcing.domain.model.aggregate#AggregateRoot.Discarded'
    assert '"timestamp":' in items[3].state


Close
-----

It is useful to unsubscribe any handlers subscribed by the
policies (avoids dangling handlers being called inappropriately,
if the process isn't going to terminate immediately, such as
when this documentation is tested as part of the library's
test suite).

.. code:: python

    # Clean up.
    app.close()


.. Todo: Something about the library's application class?

.. Todo: Something about using uuid5 to make UUIDs from things like email addresses.

.. Todo: Something about using application log to get a sequence of all events.

.. Todo: Something about using a policy to update views from published events.

.. Todo: Something about using a policy to update a register of existant IDs from published events.

.. Todo: Something about having a worker application, that has policies that process events received by a worker.

.. Todo: Something about having a policy to publish events to worker applications.

.. Todo: Something like a message queue strategy strategy.

.. Todo: Something about publishing events to a message queue.

.. Todo: Something about receiving events in a message queue worker.

.. Todo: Something about publishing events to a message queue.

.. Todo: Something about receiving events in a message queue worker.

