================================
Tutorial - Part 3 - Applications
================================


As we saw in :doc:`Part 1 </topics/tutorial/part1>`, we can
use the library's ``Application`` class to define event-sourced
applications. A subclass of ``Application`` will usually
define methods which evolve and present the state of the
application.

For example, the ``DogSchool`` class has ``register_dog()``
and ``add_trick()`` methods, which are command methods that evolve the state
of the application. It also has a ``get_tricks()`` method, which is a query
method that presents something of the state of the application without evolving
the state. These methods depend on the ``Dog`` aggregate, shown below.

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
            dog.add_trick(trick)
            self.save(dog)

        def get_tricks(self, dog_id):
            dog = self.repository.get(dog_id)
            return dog.tricks


    class Dog(Aggregate):
        @event('Started')
        def __init__(self, name):
            self.name = name
            self.tricks = []

        @event('TrickAdded')
        def add_trick(self, trick):
            self.tricks.append(trick)


We can construct an application object, and call its methods.

.. code-block:: python

    application = DogSchool()

    dog_id = application.register_dog('Fido')
    application.add_trick(dog_id, 'roll over')
    application.add_trick(dog_id, 'fetch ball')
    application.add_trick(dog_id, 'play dead')

    tricks = application.get_tricks(dog_id)

    assert tricks == ['roll over', 'fetch ball', 'play dead']


Let's explore how this works in more detail.


Applications in more detail
===========================

An application object brings together an event-sourced domain model comprised
of many event-sourced aggregates and a persistence mechanism that allows
aggregates to be "saved" and "retrieved". We can construct an application object
by calling an application class.

.. code-block:: python

    application = DogSchool()
    assert isinstance(application, Application)


An application object has a ``save()`` method, and it has a ``repository`` that has
a ``get()`` method. As we can see from the ``DogSchool`` example, an application's
methods can use the application's ``save()`` method to "save" aggregates that
have been created or updated. And they can use the application repository's ``get()``
method to "retrieve" aggregates that have been previously saved.

.. code-block:: python

    assert application.save
    assert application.repository
    assert application.repository.get


An application has a ``save()`` method. An application's ``save()`` method can be called
with one or many aggregates as its arguments. The ``save()`` method collects new events
from these aggregates by calling the ``collect_events()`` method on each aggregate
(see :doc:`Part 2 </topics/tutorial/part2>`). It puts all of the aggregate events that
it has collected into an "event store", with the guarantee that all or none of the aggregate
events will be stored. When the events cannot be saved, an exception will be raised. The
``save()`` method is used by the command methods of an application.

An application has a ``repository`` that has a ``get()`` method. The repository's
``get()`` method is called with an aggregate ID. It uses the given ID to select
aggregate events from an event store. It reconstructs the aggregate from these
events, and returns the reconstructed aggregate to the caller. The ``get()`` method
is used by both the command and the query methods of an application.


Event store
===========

An application object has an event store. When an application puts new aggregate events
into the event store, the event store uses a "mapper" to convert aggregate events to a
common type of object used to store events. These objects are referred to as "stored events".
The event store then uses a "recorder" to write the stored event objects into a database.

The event store's mapper uses a "transcoder" to serialize the state of aggregate events.
The transcoder may also compress and then encrypt the serialised state.

Repository
==========

An application has a repository, which is responsible for reconstructing aggregates that
have been previously saved from recorded stored events.

When a previously saved aggregate is requested, the repository selects stored events for
the aggregate from the recorder, and uses the mapper to reconstruct the aggregate events.
The mapper uses the transcoder to deserialize stored events to aggregate events.
The transcoder may also decrypt and decompress the serialised state. The repository then
uses a "projector function" to reconstruct the aggregate from its events.

Recorder
========

An application recorder adapts a particular database management system, and uses that
system to record stored events for an application, in a database for that application.

Events are recorded in two sequences: a sequence for the aggregate which originated the
event, and a sequence for the application as a whole. The positions in these sequences
are occupied uniquely. Events are written using an atomic transaction. If there is a
conflict or other kind of error when writing any of the events, then the transaction
can be rolled back and an exception can be raised.

Notification log
================

An application also has a notification log. The notification log supports selecting the
aggregate events from the application sequence as a series of "event notifications". This
allows the state of the application to be propagated beyond the application, so that the
events can be processed in a reliable way.

Command methods
===============

Let's consider the ``register_dog()`` and ``add_trick()`` methods
of the ``DogSchool`` application.

These are "command methods" because they evolve the application state, either
by creating new aggregates or by modifying existing aggregates.

Firstly, let's create a new ``Dog`` aggregate by calling ``register_dog()``.

.. code-block:: python

    dog_id = application.register_dog('Fido')

When the application command method ``register_dog()``
is called, a new ``Dog`` aggregate object is created by calling
the aggregate class. The new aggregate object is saved by calling
the application's ``save()`` method. The ID of the new aggregate
is returned to the caller.

We can evolve the state of the ``Dog`` aggregate by calling ``add_trick()``.

.. code-block:: python

    application.add_trick(dog_id, trick='roll over')
    application.add_trick(dog_id, trick='fetch ball')
    application.add_trick(dog_id, trick='play dead')

When the application command method ``add_trick()`` is called with
the ID of an aggregate, the ``get()`` method of the ``repository`` is
used to get the aggregate, the aggregate's ``add_trick()`` method is
called with the given value of ``trick``, and the aggregate is then
saved by calling the application's ``save()`` method.


Query methods
=============

Let's consider the ``get_tricks()`` method of the ``DogSchool`` application.
This method is a "query method" because it presents application state
without making any changes.

We can access the state of a ``Dog`` aggregate by calling ``get_tricks()``.

.. code-block:: python

    tricks = application.get_tricks(dog_id)
    assert tricks == ['roll over', 'fetch ball', 'play dead']


When the application query method ``get_tricks()`` is called with
the ID of an aggregate, the repository's ``get()`` method is used
to reconstruct the aggregate from its events. The value of the
aggregate's ``tricks`` attribute is returned to the caller.


Event notifications
===================

The limitation of application query methods is that they can only
query the aggregate sequences. Often, users of your application will
need views of the application state that depend on more sophisticated
queries. To support these queries, it is sometimes desirable to "project" the
state of the application as a whole into "materialised views" that are specifically
designed to support such queries.

In order to do this, we must be able to propagate the state of the application
as a whole, whilst avoiding the "dual writing" problem. This firstly requires
recording all the aggregate evens of an application in a sequence for the application
as a whole.

As mentioned above, an application object has a ``notification_log`` attribute.
The notification log presents all the aggregate events of an application
in the order they were stored as a sequence of "event notifications". An
event notification is nothing more than a stored event that also has a
"notification ID".

The ``select()`` method of the notification log can be used
to obtain a selection of the application's event notifications.
The ``start`` and ``limit`` arguments can be used to progressively
read all of a potentially very large number of event notifications.

.. code-block:: python

    # First page.
    notifications = application.notification_log.select(
        start=1, limit=2
    )
    assert [n.id for n in notifications] == [1, 2]

    assert 'Dog.Started' in notifications[0].topic
    assert b'Fido' in notifications[0].state
    assert dog_id == notifications[0].originator_id

    assert 'Dog.TrickAdded' in notifications[1].topic
    assert b'roll over' in notifications[1].state
    assert dog_id == notifications[1].originator_id

    # Next page.
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


This is discussed further in the :ref:`application module documentation <Notification log>`
and the `system module documentation <system.html>`_.

Database configuration
======================

An application object can be configured to work with different databases.
By default, the application stores aggregate events in memory as "plain old Python objects".
The library also supports storing events in :ref:`SQLite and PostgreSQL databases <Persistence>`.

Other databases are available. See the library's
`extension projects <https://github.com/pyeventsourcing>`__
for more information about what is currently supported.

See also the :ref:`application module documentation <Application environment>`
for more information about configuring applications using environment
variables.

The ``test()`` function below demonstrates the example ``DogSchool``
application in more detail, by creating many aggregates in one
application, by reading event notifications from the application log,
by retrieving historical versions of an aggregate, and so on. The
optimistic concurrency control, and the compression and encryption
features are also demonstrated. The steps are commented for greater
readability. The ``test()`` function will be used several times
with different configurations of persistence for our application
object: with "plain old Python objects", with SQLite, and then
with PostgreSQL.

.. code-block:: python

    from eventsourcing.persistence import IntegrityError
    from eventsourcing.system import NotificationLogReader


    def test(app: DogSchool, expect_visible_in_db: bool):
        # Check app has zero event notifications.
        assert len(app.notification_log['1,10'].items) == 0

        # Create a new aggregate.
        dog_id = app.register_dog('Fido')

        # Execute application commands.
        app.add_trick(dog_id, 'roll over')
        app.add_trick(dog_id, 'fetch ball')

        # Check recorded state of the aggregate.
        assert app.get_tricks(dog_id) == [
            'roll over',
            'fetch ball'
        ]

        # Execute another command.
        app.add_trick(dog_id, 'play dead')

        # Check recorded state of the aggregate.
        assert app.get_tricks(dog_id) == [
            'roll over',
            'fetch ball',
            'play dead'
        ]

        # Check values are (or aren't visible) in the database.
        tricks = [b'roll over', b'fetch ball', b'play dead']
        if expect_visible_in_db:
            expected_num_visible = len(tricks)
        else:
            expected_num_visible = 0

        actual_num_visible = 0
        reader = NotificationLogReader(app.notification_log)
        for notification in reader.read(start=1):
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
        notifications = list(reader.read(start=1))
        assert len(notifications) == 4

        # Optimistic concurrency control (no branches).
        old.add_trick('future')
        try:
            app.save(old)
        except IntegrityError:
            pass
        else:
            raise Exception("Shouldn't get here")

        # Check app still has only four event notifications.
        notifications = list(reader.read(start=1))
        assert len(notifications) == 4

        # Create eight more aggregate events.
        dog_id = app.register_dog('Millie')
        app.add_trick(dog_id, 'shake hands')
        app.add_trick(dog_id, 'fetch ball')
        app.add_trick(dog_id, 'sit pretty')

        dog_id = app.register_dog('Scrappy')
        app.add_trick(dog_id, 'come')
        app.add_trick(dog_id, 'spin')
        app.add_trick(dog_id, 'stay')

        # Get the new event notifications from the reader.
        last_id = notifications[-1].id
        notifications = list(reader.read(start=last_id + 1))
        assert len(notifications) == 8

        # Get all the event notifications from the application log.
        notifications = list(reader.read(start=1))
        assert len(notifications) == 12


Development environment
=======================

We can run the test in a "development" environment using the application's
default "plain old Python objects" infrastructure which keeps stored events
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
To use the library's :ref:`SQLite module <SQLite>`,
set ``PERSISTENCE_MODULE`` to the value ``'eventsourcing.sqlite'``.
When using the library's SQLite module, the environment variable
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
Using the library's :ref:`PostgresSQL infrastructure <PostgreSQL>`
will keep stored events in a PostgresSQL database.

Please note, to use the library's PostgreSQL functionality,
please install the library with the `postgres` option (or just
install the `psycopg2` package.)

::

    $ pip install eventsourcing[postgres]

Please note, the library option `postgres_dev` will install the
`psycopg2-binary` which is much faster to install, but this option
is not recommended for production use. The binary package is a
practical choice for development and testing but in production
it is advised to use the package built from sources.

The example below also uses zlib and AES to compress and encrypt the
stored events (but this is optional). To use the library's
encryption functionality with PostgreSQL, please install the library
with both the `crypto` and the `postgres` option (or just install the
`pycryptodome` and `psycopg2` packages.)

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

    # Use Postgres infrastructure.
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

Firstly, follow the steps in this tutorial in your development environment.

* Copy the code snippets above.
* Run the application code with default "plain old Python object"
  infrastructure.
* Configure and run the application with an SQLite database.
* Create a PostgreSQL database, and configure and run the
  application with a PostgreSQL database.
* Connect to the databases with the command line clients for
  SQLite and PostgreSQL, and examine the database tables to
  observe the stored event records.

Secondly, write an application class that uses the ``Todos`` aggregate
class you created in the exercise at the end of :doc:`Part 2 </topics/tutorial/part2>`.
Run your application class with default "plain old Python object" infrastructure,
and then with SQLite, and finally with PostgreSQL. Look at the
stored event records in the database tables.


Next steps
==========

For more information about event-sourced aggregates, please read through
the :doc:`domain module documentation </topics/domain>`.
For more information about event-sourced applications, please read through
the :doc:`application module documentation </topics/application>`.
For more information about the persistence mechanism for event-sourced
applications, please read through the the
:doc:`persistence module documentation </topics/persistence>`.
