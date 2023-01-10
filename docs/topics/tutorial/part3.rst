================================
Tutorial - Part 3 - Applications
================================


As we saw in :doc:`Part 1 </topics/tutorial/part1>`, we can
use the library's :class:`~eventsourcing.application.Application` class to define event-sourced
applications.

For example, the ``DogSchool`` class has ``register_dog()``
and ``add_trick()`` methods, which are command methods that evolve the state
of the application. It also has a ``get_dog()`` method, which is a query
method that presents something of the state of the application without evolving
the state. These methods depend on the ``Dog`` aggregate class.

.. code-block:: python

    from eventsourcing.application import Application
    from eventsourcing.domain import Aggregate, event


    class DogSchool(Application):
        def register_dog(self, name):
            dog = Dog(name)
            self.save(dog)
            return dog.id

        def add_trick(self, dog_id, trick):
            dog = self.repository.get(dog_id)
            dog.add_trick(trick=trick)
            self.save(dog)

        def get_dog(self, dog_id):
            dog = self.repository.get(dog_id)
            return {'name': dog.name, 'tricks': tuple(dog.tricks)}


    class Dog(Aggregate):
        @event('Registered')
        def __init__(self, name):
            self.name = name
            self.tricks = []

        @event('TrickAdded')
        def add_trick(self, trick):
            self.tricks.append(trick)


We can construct an application object, and call its methods.

.. code-block:: python

    application = DogSchool()

    dog_id = application.register_dog(name='Fido')
    application.add_trick(dog_id, trick='roll over')
    application.add_trick(dog_id, trick='fetch ball')

    dog_details = application.get_dog(dog_id)
    assert dog_details['name'] == 'Fido'
    assert dog_details['tricks'] == ('roll over', 'fetch ball')


Let's explore how this works in more detail.


Applications in more detail
===========================

An event-sourced application brings together an event-sourced domain model,
comprising many event-sourced aggregates, and a persistence mechanism for the
aggregates. This means aggregate objects can be "saved" and later reconstructed
by the application. If the persistence mechanism uses a durable database, the
aggregate objects can be reconstructed even after the application object is
reconstructed. If the persistence mechanism uses an in-memory database, the
aggregates state will usually be lost when the application object is deleted.

We can construct an application object class instance in the usual way,
by calling the application class.

.. code-block:: python

    application = DogSchool()

    assert isinstance(application, Application)


An application object has a :func:`~eventsourcing.application.Application.save` method,
which can be used to "save" aggregates that have been newly created or changed, so that
the resulting state of the aggregate will be persisted.

.. code-block:: python

    assert application.save

The application's :func:`~eventsourcing.application.Application.save` method can be called
with one or many aggregates as its arguments. The :func:`~eventsourcing.application.Application.save`
method collects new event objects from these arguments by calling the
:func:`~eventsourcing.domain.Aggregate.collect_events` method on each aggregate
(see :doc:`Part 2 </topics/tutorial/part2>`). It puts all of the aggregate event objects
that it has collected into an "event store", with the guarantee that all or none of the
event objects will be stored. If, for some reason, the event objects cannot be saved, an
exception will be raised. The :func:`~eventsourcing.application.Application.save` method
is normally used by the command methods of an application.

An application object also has a ``repository`` object. The application's repository has a
:func:`~eventsourcing.application.Repository.get` method, which can be used to reconstruct
an aggregate object from the persisted state.

.. code-block:: python

    assert application.repository
    assert application.repository.get

The repository's :func:`~eventsourcing.application.Repository.get` method is called with an
aggregate ID argument. It uses the given aggregate ID to select aggregate events from an event
store. It reconstructs an aggregate object from these events, by calling the each event object's
:func:`~eventsourcing.domain.CanMutateAggregate.mutate` method in sequence, and then it returns
the reconstructed aggregate to the caller. The :func:`~eventsourcing.application.Repository.get`
method is normally used by both command and query methods.

As we can see from the ``DogSchool`` example, an application's command methods will need to use
the :func:`~eventsourcing.application.Application.save` method to "save" aggregates that
have been created or updated. Query methods and some command methods will need to use
the application repository's :func:`~eventsourcing.application.Repository.get` method
to reconstruct aggregates that have been previously saved.

An application object also has a ``notification_log`` object. The notification log presents
the events that have been stored in the application in the order they were saved.

.. code-block:: python

    assert application.notification_log

The notification log has a :func:`~eventsourcing.application.LocalNotificationLog.select` method,
which allows a limited number of the stored events to be selected from a particular position.

Repository
==========

An application has a repository, which is responsible for reconstructing aggregates that
have been previously saved. Aggregates are requested by ID.

The repository selects events from the event store. The repository then uses a
"projector function" to reconstruct the aggregate from its events.


Event store
===========

An application object has an event store. The event store uses a "mapper" and "recorder".

The event store uses its mapper to convert between aggregate event objects of different kinds
and "stored event" objects, a common type of object used to store aggregate event objects.

The event store uses its recorder both to record stored events in a database and to select
stored event records from the database.

When aggregate events are put into the event store, the mapper is used to convert aggregate
events to stored events, and then the recorder is used to record the stored event objects in
a database.

When retrieving events from an event store, the recorder is used to select stored events
from the database, and the mapper is used to convert stored event objects back to the original
type of aggregate event objects.

Mapper
======

The mapper has a "transcoder", which it uses to serialize and deserialize the state of aggregate
events.

The mapper may use a cipher to encrypt and decrypt the serialised state. The mapper
may use a compressor to compress and decompress the serialised state. The serialized
state may be both compressed and encrypted, or compressed but not encrypted, or encrypted
but not compressed.

Recorder
========

A recorder adapts a particular database management system, and uses that
system to record stored events for an application in a database.

Events are typically recorded in two sequences: a sequence for the aggregate which
originated the event, and a sequence for the application as a whole. The positions
in these sequences are occupied uniquely. Events are written using an atomic transaction.
If there is a conflict or other kind of error when writing any of the events, then the
transaction will be rolled back and an exception will be raised.

The aggregate sequences are used by the repository to select the events for an aggregate.

The application sequence is used by the notification log to present all the aggregates events
in the order they were recorded.

Command methods
===============

Consider the ``register_dog()`` and ``add_trick()`` methods
of the ``DogSchool`` application.

These are "command methods" because they evolve the application state, either
by creating new aggregates or by modifying existing aggregates.

Let's create a new ``Dog`` aggregate by calling ``register_dog()``.

.. code-block:: python

    dog_id = application.register_dog(name='Fido')

When the application command method ``register_dog()``
is called, a new ``Dog`` aggregate object is created by calling
the aggregate class. The new aggregate object is saved by calling
the application's :func:`~eventsourcing.application.Application.save` method. The ID of the new aggregate
is returned to the caller.

We can evolve the state of the ``Dog`` aggregate by calling ``add_trick()``.

.. code-block:: python

    application.add_trick(dog_id, trick='roll over')
    application.add_trick(dog_id, trick='fetch ball')
    application.add_trick(dog_id, trick='play dead')

When the application command method ``add_trick()`` is called with
the ID of an aggregate, the :func:`~eventsourcing.application.Repository.get` method of the ``repository`` is
used to get the aggregate. The aggregate's ``add_trick()`` method is
called with the given value of ``trick``. The aggregate is then
saved by calling the application's :func:`~eventsourcing.application.Application.save` method.


Query methods
=============

Consider the ``get_dog()`` method of the ``DogSchool`` application.

This method is a "query method" because it presents something of the
application state without making any changes.

We can access the state of a ``Dog`` aggregate by calling ``get_dog()``.

.. code-block:: python

    dog_details = application.get_dog(dog_id)

    assert dog_details['name'] == 'Fido'
    assert dog_details['tricks'] == ('roll over', 'fetch ball', 'play dead')


When the application query method ``get_dog()`` is called with
the ID of an aggregate, the repository's :func:`~eventsourcing.application.Repository.get` method is used
to reconstruct the aggregate from its events. The details of the
``Dog`` aggregate are returned to the caller.


Notification log
================

An application object has a "notification log". The notification log presents the
stored events of an application so that the state of the application can be propagated
in a reliable way.

Each event that is stored in the application is assigned an integer notification ID
when it is recorded. The notification IDs increase, so that later events have higher
notification IDs. The numbering of stored events with notification IDs orders all of
the stored events in a single sequence. This sequence is referred to as the "application sequence".

The notification log has a :func:`~eventsourcing.application.LocalNotificationLog.select` method. The
:func:`~eventsourcing.application.LocalNotificationLog.select` method can be used to obtain a subsequence
of the application sequence. The ``start`` argument of this method is used to specify the notification ID
of the first item in the selected subsequence. The ``limit`` argument is used to limit the length of the
subsequence. Successive calls to :func:`~eventsourcing.application.LocalNotificationLog.select` can be made,
so that a potentially very long (and unbound) application sequence can be progressively propagated and processed
as relatively small and manageable (fixed size) subsequences.

The example below shows how the four events we have stored so far in this example can be selected as two
subsequences, each having two event notifications. In practice, the subsequences will be slightly longer,
but in this example only four events have been stored.

.. code-block:: python

    # First subsequence of event notifications.
    notifications = application.notification_log.select(
        start=1, limit=2
    )
    assert [n.id for n in notifications] == [1, 2]

    assert 'Dog.Registered' in notifications[0].topic
    assert b'Fido' in notifications[0].state
    assert dog_id == notifications[0].originator_id

    assert 'Dog.TrickAdded' in notifications[1].topic
    assert b'roll over' in notifications[1].state
    assert dog_id == notifications[1].originator_id

    # Second subsequence of event notifications.
    notifications = application.notification_log.select(
        start=notifications[-1].id + 1, limit=2
    )
    assert [n.id for n in notifications] == [3, 4]

    assert 'Dog.TrickAdded' in notifications[0].topic
    assert b'fetch ball' in notifications[0].state
    assert dog_id == notifications[0].originator_id

    assert 'Dog.TrickAdded' in notifications[1].topic
    assert b'play dead' in notifications[1].state
    assert dog_id == notifications[1].originator_id


Why do we need to propagate the state of the application? The application query methods
can only select aggregates by ID from the repository. However, the users of your software
may need to see views of the application state that depend on more sophisticated queries.
And so it may be necessary to "project" the state of the application as a whole into
"materialised views" that are specifically designed to support more sophisticated queries.
We need to propagate the state of the application so that it can be projected into
these materialised views. You may also wish to make copies of the application state as a backup.

We can propagate the state of an event-sourced application by propagating all of the stored
events in the order they were recorded. The application state can be propagated reliably because
events are recorded within an atomic transaction in two sequences, an aggregate sequence and
the application sequence, so there will never be an event in an aggregate sequence that does not
also appear in the application sequence. This avoids the "dual writing" problem which arises when
firstly an update to application state is written to a database and separately a message is written
to a message queue: the problem being that one may happen successfully and the other may fail. This
is why event sourcing is a good foundation for building reliable distributed systems.

There is a more :ref:`detailed discussion of notification logs <Notification log>` in the
:doc:`application module </topics/application>` documentation. The propagation and processing
of event notifications is discussed further in the :doc:`system module </topics/system>` documentation.

Database configuration
======================

An :ref:`application object can be configured <Application configuration>` to work with different
database management systems. Database management systems are encapsulated for use by applications
as "persistence modules", each encapsulating a different database management system.

By default, the application stores aggregate events in memory as "plain old Python objects".
This is suitable for a development environment. An application can be :ref:`configured to use
alternative persistence modules <Persistence>`. The core library supports storing events in
SQLite and PostgreSQL. Other databases are available. See the library's `extension projects
<https://github.com/pyeventsourcing>`_ for more information about what is currently supported.

The ``test()`` function, defined below, below demonstrates the example ``DogSchool``
application in more detail. It will be executed several times, with the application
configured to use different persistence persistence modules. Firstly, it will be executed
with the application using the default "plain old Python objects" persistence module,
secondly with the library's SQLite persistence module, and then thirdly with the library's
PostgreSQL persistence module.

The ``test()`` function demonstrates creating many aggregates in one application, reading
event notifications from the application log, and retrieving historical versions of an aggregate.
The optimistic concurrency control feature, and the compression and encryption features are also
demonstrated. The steps are commented for greater readability.

.. code-block:: python

    from eventsourcing.persistence import IntegrityError

    def test(app: DogSchool, expect_visible_in_db: bool):
        # Check app has zero event notifications.
        assert len(app.notification_log.select(start=1, limit=10)) == 0

        # Create a new aggregate.
        dog_id = app.register_dog(name='Fido')

        # Execute application commands.
        app.add_trick(dog_id, trick='roll over')
        app.add_trick(dog_id, trick='fetch ball')

        # Check recorded state of the aggregate.
        dog_details = app.get_dog(dog_id)
        assert dog_details['name'] == 'Fido'
        assert dog_details['tricks'] == ('roll over', 'fetch ball')

        # Execute another command.
        app.add_trick(dog_id, trick='play dead')

        # Check recorded state of the aggregate.
        dog_details = app.get_dog(dog_id)
        assert dog_details['name'] == 'Fido'
        assert dog_details['tricks'] == ('roll over', 'fetch ball', 'play dead')

        # Check values are (or aren't visible) in the database.
        tricks = [b'roll over', b'fetch ball', b'play dead']
        if expect_visible_in_db:
            expected_num_visible = len(tricks)
        else:
            expected_num_visible = 0

        actual_num_visible = 0
        notifications = app.notification_log.select(start=1, limit=10)
        for notification in notifications:
            for trick in tricks:
                if trick in notification.state:
                    actual_num_visible += 1
                    break
        assert expected_num_visible == actual_num_visible

        # Get historical state (at version 3, before 'play dead' happened).
        old = app.repository.get(dog_id, version=3)
        assert len(old.tricks) == 2
        assert old.tricks[-1] == 'fetch ball'  # last thing to have happened was 'fetch ball'

        # Check app has four event notifications.
        notifications = app.notification_log.select(start=1, limit=10)
        assert len(notifications) == 4

        # Optimistic concurrency control (no branches).
        old.add_trick(trick='future')
        try:
            app.save(old)
        except IntegrityError:
            pass
        else:
            raise Exception("Shouldn't get here")

        # Check app still has only four event notifications.
        notifications = app.notification_log.select(start=1, limit=10)
        assert len(notifications) == 4

        # Create eight more aggregate events.
        dog_id = app.register_dog(name='Millie')
        app.add_trick(dog_id, trick='shake hands')
        app.add_trick(dog_id, trick='fetch ball')
        app.add_trick(dog_id, trick='sit pretty')

        dog_id = app.register_dog(name='Scrappy')
        app.add_trick(dog_id, trick='come')
        app.add_trick(dog_id, trick='spin')
        app.add_trick(dog_id, trick='stay')

        # Get the new event notifications from the reader.
        last_id = notifications[-1].id
        notifications = app.notification_log.select(start=last_id + 1, limit=10)
        assert len(notifications) == 8


Development environment
=======================

We can run the test in a "development" environment using the application's
default "plain old Python objects" persistence module which keeps stored events
in memory. The example below runs without compression or encryption of the
stored events. This is how the application objects have been working in this
tutorial so far.


.. code-block:: python

    # Construct an application object.
    app = DogSchool()

    # Run the test.
    test(app, expect_visible_in_db=True)


SQLite environment
==================

We can also configure an application to use SQLite for storing events.
To use the library's :ref:`SQLite persistence module <sqlite-module>`,
set ``PERSISTENCE_MODULE`` to the value ``'eventsourcing.sqlite'``.
When using the library's SQLite persistence module, the environment variable
``SQLITE_DBNAME`` must also be set. This value will be passed to Python's
:func:`sqlite3.connect`.

.. code-block:: python

    import os


    # Use SQLite for persistence.
    os.environ['PERSISTENCE_MODULE'] = 'eventsourcing.sqlite'

    # Configure SQLite database URI. Either use a file-based DB;
    os.environ['SQLITE_DBNAME'] = '/path/to/your/sqlite-db'

    # or use an in-memory DB with cache not shared, only works with single thread;
    os.environ['SQLITE_DBNAME'] = ':memory:'

    # or use an unnamed in-memory DB with shared cache, works with multiple threads;
    os.environ['SQLITE_DBNAME'] = 'file::memory:?mode=memory&cache=shared'

    # or use a named in-memory DB with shared cache, to create distinct databases.
    os.environ['SQLITE_DBNAME'] = 'file:application1?mode=memory&cache=shared'

    # Set optional lock timeout (default 5s).
    os.environ['SQLITE_LOCK_TIMEOUT'] = '10'  # seconds


Having configured the application with these environment variables, we
can construct the application and run the test using SQLite.

.. code-block:: python

    # Construct an application object.
    app = DogSchool()

    # Run the test.
    test(app, expect_visible_in_db=True)


In this example, stored events are neither compressed nor encrypted. In consequence,
we can expect the recorded values to be visible in the database records.


PostgreSQL environment
======================

We can also configure a "production" environment to use PostgreSQL.
Using the library's :ref:`PostgresSQL persistence module <postgres-module>`
will keep stored events in a PostgresSQL database.

To use the library's PostgreSQL persistence module, either install the
library with the ``postgres`` option, or install the ``psycopg2`` package
directly.

::

    $ pip install eventsourcing[postgres]

Please note, the library option ``postgres_dev`` will install the
``psycopg2-binary`` which is much faster to install, but this option
is not recommended for production use. The binary package is a
practical choice for development and testing but in production
it is advised to use the package built from sources.

The example below also uses zlib and AES to compress and encrypt the
stored events. To use the library's encryption functionality,
either install the library with the ``crypto`` option, or install the
``pycryptodome`` directly.

::

    $ pip install eventsourcing[crypto]

Both the ``crypto`` and the ``postgres`` options can be installed together
with the following command.

::

    $ pip install eventsourcing[crypto,postgres]


It is assumed for this example that the database and database user have
already been created, and the database server is running locally.

.. code-block:: python

    import os

    from eventsourcing.cipher import AESCipher

    # Generate a cipher key (keep this safe).
    cipher_key = AESCipher.create_key(num_bytes=32)

    # Cipher key.
    os.environ['CIPHER_KEY'] = cipher_key
    # Cipher topic.
    os.environ['CIPHER_TOPIC'] = 'eventsourcing.cipher:AESCipher'
    # Compressor topic.
    os.environ['COMPRESSOR_TOPIC'] = 'eventsourcing.compressor:ZlibCompressor'

    # Use Postgres database.
    os.environ['PERSISTENCE_MODULE'] = 'eventsourcing.postgres'

    # Configure database connections.
    os.environ['POSTGRES_DBNAME'] = 'eventsourcing'
    os.environ['POSTGRES_HOST'] = '127.0.0.1'
    os.environ['POSTGRES_PORT'] = '5432'
    os.environ['POSTGRES_USER'] = 'eventsourcing'
    os.environ['POSTGRES_PASSWORD'] = 'eventsourcing'

Having configured the application with these environment variables,
we can construct the application and run the test using PostgreSQL.


.. code-block:: python

    # Construct an application object.
    app = DogSchool()

    # Run the test.
    test(app, expect_visible_in_db=False)

In this example, stored events are both compressed and encrypted. In consequence,
we can expect the recorded values not to be visible in the database records.


Exercise
========

Firstly, replicate the code in this tutorial in your development environment.

* Copy the code snippets above.
* Run the application code with the default "plain old Python object"
  persistence module.
* Configure and run the application with an SQLite database.
* Create a PostgreSQL database, and configure and run the
  application with a PostgreSQL database.
* Connect to the databases with the command line clients for
  SQLite and PostgreSQL, and examine the database tables to
  observe the stored event records.

Secondly, write an application class that uses the ``Todos`` aggregate
class you created in the exercise at the end of :doc:`Part 2 </topics/tutorial/part2>`.
Run your application class with default "plain old Python object" persistence module,
and then with an SQLite database, and finally with a PostgreSQL database. Look at the
stored event records in the database tables.


Next steps
==========

* For more information about event-sourced applications, please read the
  :doc:`the application module documentation </topics/domain>`.
* For more information about storing and retrieving domain events, please read
  the :doc:`persistence module documentation </topics/persistence>`.
