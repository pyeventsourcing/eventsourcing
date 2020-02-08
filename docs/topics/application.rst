=================
Application layer
=================

This section discusses how an :doc:`event-sourced domain model
</topics/domainmodel>` can be combined with :doc:`library infrastructure
</topics/infrastructure>` to make an event sourced application. The
normal layered architecture of an enterprise
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
:class:`~eventsourcing.application.simple.SimpleApplication`. This
application class is independent of infrastructure, and as such
can be used to define applications independently of infrastructure,
but also can't be constructed directly.

For that reason, the example below uses a subclass that depends on SQLAlchemy.
The base class is extended by
:class:`~eventsourcing.application.sqlalchemy.SQLAlchemyApplication`
which uses SQLAlchemy to store and retrieve domain event records.


Application object
------------------

The SQLAlchemy application class has a ``uri`` constructor argument,
which is an (SQLAlchemy-style) database connection string. The example
below uses SQLite with an in-memory database (which is also the default).
You can use any valid connection string.

.. code:: python

    uri = 'sqlite:///:memory:'


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
    mysql+pymysql://scott:tiger@hostname/dbname?charset=utf8mb4&binary_prefix=true

    # MySQL with mysql-connector-python-rf.
    mysql+sqlconnector://scott:tiger@hostname/dbname

In case you were wondering, the ``uri`` value is used to construct
an SQLAlchemy thread-scoped session facade.

Instead of providing a ``uri`` value, an already existing SQLAlchemy
session can be passed in, using constructor argument ``session``.
For example, a session object provided by a framework integrations such as
`Flask-SQLAlchemy <http://flask-sqlalchemy.pocoo.org/>`__ could be passed
to the application object.

Encryption is optionally enabled in
:class:`~eventsourcing.application.simple.SimpleApplication`
with a suitable AES key (16, 24, or 32 random bytes encoded as Base64).

.. code:: python

    from eventsourcing.utils.random import encoded_random_bytes

    # Keep this safe (random bytes encoded with Base64).
    cipher_key = encoded_random_bytes(num_bytes=32)


These values can be given to the application object as constructor arguments
``uri`` and ``cipher_key``. The ``persist_event_type`` value determines which
types of domain event will be persisted by the application. So that different
applications can be constructed in the same process, the default value of
``persist_event_type`` is ``None``.

.. code:: python

    from eventsourcing.application.sqlalchemy import SQLAlchemyApplication
    from eventsourcing.domain.model.aggregate import AggregateRoot

    application = SQLAlchemyApplication(
        uri='sqlite:///:memory:',
        cipher_key=cipher_key,
        persist_event_type=AggregateRoot.Event,
    )


Alternatively, the ``uri`` value can be set as environment variable ``DB_URI``,
and the ``cipher_key`` value can be set as environment variable
``CIPHER_KEY``.


Event store
-----------

Once constructed, the application object has an event store, provided
by the library's :class:`~eventsourcing.infrastructure.eventstore.EventStore`
class.

.. code:: python

    from eventsourcing.infrastructure.eventstore import EventStore

    assert isinstance(application.event_store, EventStore)


Persistence policy
------------------

The ``application`` has a persistence policy, an instance of the library class
:class:`~eventsourcing.application.policies.PersistencePolicy`. The persistence policy
uses the event store.

.. code:: python

    from eventsourcing.application.policies import PersistencePolicy

    assert isinstance(application.persistence_policy, PersistencePolicy)

The persistence policy will only persist particular types of domain events.
The application class attribute `persist_event_type` is used to define which
classes of domain events will be persisted by the application's persistence
policy.


Repository
----------

The ``application`` also has a repository, an instance of the library class
:class:`~eventsourcing.infrastructure.eventsourcedrepository.EventSourcedRepository`.
The repository is generic, and can retrieve all aggregates in an application,
regardless of their class. That is, there aren't different repositories for
different types of aggregate in this application. The repository also uses
the event store.

.. code:: python

    from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository

    assert isinstance(application.repository, EventSourcedRepository)


The library class :class:`~eventsourcing.domain.model.aggregate.AggregateRoot`
can be used directly to create a new aggregate object that is available in the
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


Notification log
----------------

The :class:`~eventsourcing.application.simple.SimpleApplication` has a
``notification_log`` attribute, which can be used to follow the application
events as a single sequence.

.. code:: python

    # Follow application event notifications.
    from eventsourcing.application.notificationlog import NotificationLogReader
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

Firstly, a custom aggregate root class called ``CustomAggregate`` is defined
below. It extends the library's :class:`~eventsourcing.domain.model.aggregate.AggregateRoot`
entity with event-sourced attribute ``a``.

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

The example below shows a custom application class ``MyApplication`` that
extends :class:`~eventsourcing.application.sqlalchemy.SQLAlchemyApplication`
with application service ``create_aggregate()`` that can create new
``CustomAggregate`` entities.

The ``persist_event_type`` value can be set as a class attribute.

.. code:: python

    from eventsourcing.application.sqlalchemy import SQLAlchemyApplication


    class MyApplication(SQLAlchemyApplication):
        persist_event_type = AggregateRoot.Event

        def create_aggregate(self, a):
            return CustomAggregate.__create__(a=1)


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

You can list the domain events of an aggregate
by using the method
:func:`~eventsourcing.infrastructure.base.AbstractEventStore.list_events`
of the event store of the application.

.. code:: python

    events = application.event_store.list_events(originator_id=aggregate.id)
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
by using the method
:func:`~eventsourcing.infrastructure.base.AbstractRecordManager.get_items`
of the event store's record manager.

.. code:: python

    items = application.event_store.record_manager.list_items(aggregate.id)
    assert len(items) == 4

    assert items[0].originator_id == aggregate.id
    assert items[0].topic == 'eventsourcing.domain.model.aggregate#AggregateRoot.Created'
    assert '"a":1' in items[0].state.decode('utf8'), items[0].state
    assert b'"timestamp":' in items[0].state

    assert items[1].originator_id == aggregate.id
    assert items[1].topic == 'eventsourcing.domain.model.aggregate#AggregateRoot.AttributeChanged'
    assert b'"name":"_a"' in items[1].state
    assert b'"timestamp":' in items[1].state

    assert items[2].originator_id == aggregate.id
    assert items[2].topic == 'eventsourcing.domain.model.aggregate#AggregateRoot.AttributeChanged'
    assert b'"name":"_a"' in items[2].state
    assert b'"timestamp":' in items[2].state

    assert items[3].originator_id == aggregate.id
    assert items[3].topic == 'eventsourcing.domain.model.aggregate#AggregateRoot.Discarded'
    assert b'"timestamp":' in items[3].state

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

    assert len(event_records) == 4, len([r.originator_id for r in event_records])

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
