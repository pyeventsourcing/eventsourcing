===========
Application
===========

This section discusses how an event sourced domain model can
be combined with library infrastructure to make an event sourced
application. The normal layered architecture of an enterprise
application is followed: an application layer supports an interface
layer and depends on both a :doc:`domain layer </topics/domainmodel>`
and an :doc:`infrastructure layer </topics/infrastructure>`.


.. contents:: :local:


Overview
========


In this library, an application object has an event store which encapsulates
infrastructure required to store the state of an application as a sequence of
domain events. An application also has a persistence subscriber, a repository,
and a notification log. The event store is used by the repository and notification
log to retrieve events, and by the persistence subscriber to store events.

The state of an application is partitioned across a set of event-sourced "aggregates"
(domain entities). Each aggregate has a unique ID, and the state of an aggregate is
determined by a sequence of domain events. Aggregates implement commands which
trigger domain events that mutate the state of their aggregate by augmenting the
aggregate's sequence of events. The repository of an application allows individual
aggregates of the application to be retrieved by ID, optionally at a particular version.

An application object can have methods ("application services")
which provide a relatively simple interface for client operations,
hiding the complexity and usage of the application's domain and
infrastructure layers.

Application services can be developed outside-in, with a
test- or behaviour-driven development approach. A test suite can
be imagined as an interface that uses the application. Interfaces
are outside the scope of the application layer.

To run the examples below, please install the library with the
'sqlalchemy' option.

::

    $ pip install eventsourcing[sqlalchemy]


Simple application
==================

The library provides an abstract base class for applications called
:class:`~eventsourcing.application.simple.SimpleApplication`.

The base class is extended by
:class:`~eventsourcing.application.sqlalchemy.SQLAlchemyApplication`
which uses SQLAlchemy to store and retrieve domain event records. Its
``uri`` constructor argument is an SQLAlchemy-style database connection
string. An SQLAlchemy thread-scoped session facade will be setup using
the ``uri`` value.

.. code:: python

    uri = 'sqlite:///:memory:'


As you can see, this example is using SQLite to manage
an in memory relational database (which is also the default).
You can change ``uri`` to any valid connection string.

Here are some example connection strings: for an SQLite
file; for a PostgreSQL database; or for a MySQL database.
See SQLAlchemy's create_engine() documentation for details.
You may need to install drivers for your database management
system (such as ``psycopg2`` for PostreSQL or ``pymysql`` or
even ``mysql-connector-python-rf`` for MySQL).

::

    # SQLite with a file on disk.
    sqlite:////tmp/mydatabase

    # PostgreSQL with psycopg2.
    postgresql+psycopg2://scott:tiger@localhost:5432/mydatabase

    # MySQL with pymysql.
    mysql+pymysql://scott:tiger@hostname/dbname

    # MySQL with mysql-connector-python-rf.
    mysql+sqlconnector://scott:tiger@hostname/dbname


Encryption is optionally enabled in
:class:`~eventsourcing.application.simple.SimpleApplication`
with a suitable AES key (16, 24, or 32 random bytes encoded as Base64).

.. code:: python

    from eventsourcing.utils.random import encode_random_bytes

    # Keep this safe (random bytes encoded with Base64).
    cipher_key = encode_random_bytes(num_bytes=32)

These values can be given to the application object as
constructor arguments ``uri`` and ``cipher_key``. Alternatively,
the ``uri`` value can be set as environment variable ``DB_URI``,
and the ``cipher_key`` value can be set as environment variable
``CIPHER_KEY``.

.. code:: python

    from eventsourcing.application.sqlalchemy import SQLAlchemyApplication
    from eventsourcing.domain.model.aggregate import AggregateRoot

    application = SQLAlchemyApplication(
        uri='sqlite:///:memory:',
        cipher_key=cipher_key,
        persist_event_type=AggregateRoot.Event,
    )


Instead of providing a URI, an already existing SQLAlchemy
session can be passed in, using constructor argument ``session``.
For example, a session object provided by a framework extension such as
`Flask-SQLAlchemy <http://flask-sqlalchemy.pocoo.org/>`__ could be passed
to the application object.

Once constructed, the application object will have an event store, provided
by the library's :class:`~eventsourcing.infrastructure.eventstore.EventStore`
class.

.. code:: python

    application.event_store

The ``application`` also has a persistence policy, provided by the
library's :class:`~eventsourcing.application.policies.PersistencePolicy` class.

.. code:: python

    application.persistence_policy

The persistence policy appends domain events of type `persist_event_type`
to its event store whenever they are published.

The :class:`~eventsourcing.application.simple.SimpleApplication` also has a
repository, an instance of the library class
:class:`~eventsourcing.infrastructure.eventsourcedrepository.EventSourcedRepository`.

.. code:: python

    application.repository

Both the repository and persistence policy use the event store.

The aggregate repository is generic, and can retrieve all
aggregates in an application, regardless of their class.

The example below uses the library class
:class:`~eventsourcing.domain.model.aggregate.AggregateRoot`
directly to create a new aggregate object that is available in the
application's repository.

.. code:: python

    obj = AggregateRoot.__create__()
    obj.__change_attribute__(name='a', value=1)
    assert obj.a == 1
    obj.__save__()

    # Check the repository has the latest values.
    copy = application.repository[obj.id]
    assert copy.a == 1

    # Check the aggregate can be discarded.
    copy.__discard__()
    copy.__save__()
    assert copy.id not in application.repository

    # Check optimistic concurrency control is working ok.
    from eventsourcing.exceptions import ConcurrencyError
    try:
        obj.__change_attribute__(name='a', value=2)
        obj.__save__()
    except ConcurrencyError:
        pass
    else:
        raise Exception("Shouldn't get here")

Because of the unique constraint on the sequenced item table, it isn't
possible to branch the evolution of an entity and store two events
at the same version. Hence, if the entity you are working on has been
updated elsewhere, an attempt to update your object will cause a
``ConcurrencyError`` exception to be raised.

Concurrency errors can be avoided if all commands for a single aggregate
are executed in series, for example by treating each aggregate as an actor,
within an actor framework.

The :class:`~eventsourcing.application.simple.SimpleApplication` has a
``notification_log`` attribute, which can be used to follow the application
events as a single sequence.

.. code:: python

    # Follow application event notifications.
    from eventsourcing.interface.notificationlog import NotificationLogReader
    reader = NotificationLogReader(application.notification_log)
    notification_ids = [n['id'] for n in reader.read()]
    assert notification_ids == [1, 2, 3], notification_ids

    # - create two more aggregates
    obj = AggregateRoot.__create__()
    obj.__save__()

    obj = AggregateRoot.__create__()
    obj.__save__()

    # - get the new event notifications from the reader
    notification_ids = [n['id'] for n in reader.read()]
    assert notification_ids == [4, 5], notification_ids

Custom application
==================

The library class :class:`~eventsourcing.application.simple.SimpleApplication`
can be extended. The example below shows a custom application class ``MyApplication`` that
extends ``SQLAlchemyApplication`` with application service ``create_aggregate()``
that can create new ``CustomAggregate`` entities.

.. code:: python

    from eventsourcing.application.sqlalchemy import SQLAlchemyApplication


    class MyApplication(SQLAlchemyApplication):
        def __init__(self, **kwargs):
            super(MyApplication, self).__init__(
                persist_event_type=CustomAggregate.Event, **kwargs)

        def create_aggregate(self, a):
            return CustomAggregate.__create__(a=1)


The application code above depends on an entity class called
``CustomAggregate``, which is defined below. It extends the
library's :class:`~eventsourcing.domain.model.aggregate.AggregateRoot`
entity with an event sourced, mutable attribute ``a``.

.. code:: python

    from eventsourcing.domain.model.decorators import attribute

    class CustomAggregate(AggregateRoot):
        def __init__(self, a, **kwargs):
            super(CustomAggregate, self).__init__(**kwargs)
            self._a = a

        @attribute
        def a(self):
            """Mutable attribute a."""


For more sophisticated domain models, please read about the custom
entities, commands, and domain events that can be developed using
classes from the library's :doc:`domain model layer </topics/domainmodel>`.


Run the code
------------

The custom application object can be constructed.

.. code:: python

    # Construct application object.
    application = MyApplication(uri='sqlite:///:memory:')


The application service aggregate factor method ``create_aggregate()``
can be called.

.. code:: python

    # Create aggregate using application service, and save it.
    aggregate = application.create_aggregate(a=1)
    aggregate.__save__()


Existing aggregates can be retrieved by ID using the repository's
dictionary-like interface.

.. code:: python

    # Aggregate is in the repository.
    assert aggregate.id in application.repository

    # Get aggregate using dictionary-like interface.
    aggregate = application.repository[aggregate.id]

    assert aggregate.a == 1


Changes to the aggregate's attribute ``a`` are visible in
the repository once pending events have been published.

.. code:: python

    # Change attribute value.
    aggregate.a = 2
    aggregate.a = 3

    # Don't forget to save!
    aggregate.__save__()

    # Retrieve again from repository.
    aggregate = application.repository[aggregate.id]

    # Check attribute has new value.
    assert aggregate.a == 3


The aggregate can be discarded. After being saved, a discarded
aggregate will no longer be available in the repository.

.. code:: python

    # Discard the aggregate.
    aggregate.__discard__()
    aggregate.__save__()

    # Check discarded aggregate no longer exists in repository.
    assert aggregate.id not in application.repository


Attempts to retrieve an aggregate that does not
exist will cause a ``KeyError`` to be raised.

.. code:: python

    # Fail to get aggregate from dictionary-like interface.
    try:
        application.repository[aggregate.id]
    except KeyError:
        pass
    else:
        raise Exception("Shouldn't get here")


Stored events
-------------

It is always possible to get the domain events for an aggregate,
by using the application's event store method ``get_domain_events()``.

.. code:: python

    events = application.event_store.get_domain_events(originator_id=aggregate.id)
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

It is also possible to get the sequenced item namedtuples for an aggregate,
by using the method ``get_items()`` of the event store's record manager.

.. code:: python

    items = application.event_store.record_manager.list_items(aggregate.id)
    assert len(items) == 4

    assert items[0].originator_id == aggregate.id
    assert items[0].event_type == 'eventsourcing.domain.model.aggregate#AggregateRoot.Created'
    assert '"a":1' in items[0].state, items[0].state
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

In this example, the ``cipher_key`` was not set, so the stored data is visible.

Database records
----------------

Of course, it is also possible to just use the record class directly
to obtain records. After all, it's just an SQLAlchemy ORM object.

.. code:: python

    application.event_store.record_manager.record_class

The ``orm_query()`` method of the SQLAlchemy record manager
is a convenient way to get a query object from the session
for the record class.

.. code:: python

    event_records = application.event_store.record_manager.orm_query().all()

    assert len(event_records) == 4

Close
-----

If the application isn't being used as a context manager, then it is useful to
unsubscribe any handlers subscribed by the policies (avoids dangling handlers
being called inappropriately, if the process isn't going to terminate immediately,
such as when this documentation is tested as part of the library's test suite).

.. code:: python

    # Clean up.
    application.close()



.. Todo: Something about using uuid5 to make UUIDs from things like email addresses.

.. Todo: Something about using a policy to update views from published events.

.. Todo: Something about using a policy to update a register of existant IDs from published events.

.. Todo: Something about having a worker application, that has policies that process events received by a worker.

.. Todo: Something about having a policy to publish events to worker applications.

.. Todo: Something like a message queue strategy strategy.

.. Todo: Something about publishing events to a message queue.

.. Todo: Something about receiving events in a message queue worker.

.. Todo: Something about publishing events to a message queue.

.. Todo: Something about receiving events in a message queue worker.

