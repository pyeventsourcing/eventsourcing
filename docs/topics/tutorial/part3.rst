=================
Tutorial - Part 3
=================

As we saw in :doc:`Part 1 </topics/tutorial/part1>`, we can
use the application base class ``Application`` to define
event-sourced applications in Python.

.. code-block:: python

    from eventsourcing.application import Application
    from eventsourcing.domain import Aggregate, event


    class Universe(Application):
        def create_world(self, name):
            world = World(name)
            self.save(world)
            return world.id

        def make_it_so(self, world_id, what):
            world = self._get_world(world_id)
            world.make_it_so(what)
            self.save(world)

        def get_history(self, world_id):
            return self._get_world(world_id).history

        def _get_world(self, world_id):
            return self.repository.get(world_id)


    class World(Aggregate):
        @event('Started')
        def __init__(self, name):
            self.name = name
            self.history = []

        @event('SomethingHappened')
        def make_it_so(self, what) -> None:
            self.history.append(what)


We can create an application object, and call its methods.

.. code-block:: python

    application = Universe()

    world_id = application.create_world('Earth')
    application.make_it_so(world_id, 'dinosaurs')
    application.make_it_so(world_id, 'trucks')
    application.make_it_so(world_id, 'internet')

    history = application.get_history(world_id)
    assert history == ['dinosaurs', 'trucks', 'internet']


Let's explore how this works in more detail.


Applications in more detail
===========================

An application object in this library roughly corresponds to a "bounded context"
in Domain-Driven Design. An application can have aggregates of different types in
its domain model. They are accessed and manipulated with commands and queries.
An application also has a persistence mechanism for storing and retrieving aggregate
events.

As we saw in the example above, we can construct an application object by calling
an application class. The example above defines an event-sourced application named
``Universe``. The application class uses the application base class
``Application``. When the application class is called, an application
object is constructed.

.. code-block:: python

    application = Universe()

The ``Universe`` application class has a command method ``create_world()``
that creates and saves new instances of the aggregate class ``World``. It has a
command method ``make_it_so()`` that calls the aggregate command method
``make_it_so()`` of an already existing aggregate object. And it
has a query method ``get_history()`` that returns the ``history`` of
an aggregate object.

Command methods
===============

When the application command method ``create_world()`` is called,
a new ``World`` aggregate object is created, the new aggregate
object is saved by calling the application's ``save()`` method,
and then the ID of the aggregate is returned to the caller.

Let's create a new aggregate by calling the application method ``create_world()``.

.. code-block:: python

    world_id = application.create_world('Earth')


We can evolve the state of the application's aggregate by calling the
application command method ``make_it_so()``.

When the application command method ``make_it_so()`` is called with
the ID of an aggregate, the repository is used to get the
aggregate, the aggregate's ``make_it_so()`` method is called with
the given value of ``what``, and the aggregate is saved by calling
the application's ``save()`` method.

.. code-block:: python

    application.make_it_so(world_id, 'dinosaurs')
    application.make_it_so(world_id, 'trucks')
    application.make_it_so(world_id, 'internet')


Query methods
=============

We can access the state of the application's aggregate by calling the
application query method ``get_history()``.

.. code-block:: python

    history = application.get_history(world_id)
    assert history == ['dinosaurs', 'trucks', 'internet']


When the application query method ``get_history()`` is called with
the ID of an aggregate, the repository is used to get the
aggregate, and the value of the aggregate's ``history`` attribute
is returned to the caller.


Event notifications
===================

The ``Application`` class also has a ``log`` attribute,
which is a 'notification log' (aka the 'outbox pattern').

The notification log can be used to propagate the state of
the application in a manner that supports deterministic
processing of the application state in event-driven systems.
It presents all the aggregate events that have been stored
across all the aggregates of an application as a sequence of
event notifications.

The log presents the aggregate events in the order in which
they were stored. Each of the event notifications has an integer
ID which increases along the sequence.


.. code-block:: python

    notifications = application.log.select(start=1, limit=4)
    assert [n.id for n in notifications] == [1, 2, 3, 4]

    assert 'World.Started' in notifications[0].topic
    assert b'Earth' in notifications[0].state
    assert world_id == notifications[0].originator_id

    assert 'World.SomethingHappened' in notifications[1].topic
    assert b'dinosaurs' in notifications[1].state
    assert world_id == notifications[1].originator_id

    assert 'World.SomethingHappened' in notifications[2].topic
    assert b'trucks' in notifications[2].state
    assert world_id == notifications[2].originator_id

    assert 'World.SomethingHappened' in notifications[3].topic
    assert b'internet' in notifications[3].state
    assert world_id == notifications[3].originator_id


How does it work?
=================

The ``Application`` class provides persistence infrastructure that can
collect, serialise, and store aggregate events. It can also reconstruct
aggregates from stored events.

The application ``save()`` method saves aggregates by
collecting and storing pending aggregate events. The ``save()``
method calls the given aggregate's ``collect_events()`` method and
puts the pending aggregate events in an event store, with a
guarantee that either all the events will be stored or none of
them will be.

The application ``repository`` has a ``get()``
method that can be used to obtain previously saved aggregates.
The ``get()`` method is called with an aggregate ID. It retrieves
stored events for an aggregate from an event store, then
reconstructs the aggregate object from its previously stored
events (see above), and then returns the reconstructed aggregate object to
the caller.

The application class can be configured using
environment variables to work with different databases, and
optionally to encrypt and compress stored events. By default,
the application serialises aggregate events using JSON, and
stores them in memory as "plain old Python objects". The library
includes support for storing events in SQLite and PostgreSQL (see
below). Other databases are available.


Persistence mechanisms
======================

An event-sourced application has a mechanism for storing
and retrieving events. Events can be stored in different
ways. An application object can be configured to use one
of many different ways of storing and retrieving events.

The ``test()`` function below demonstrates the example in more detail,
by creating many aggregates in one application, reading event
notifications from the application log, retrieving historical
versions of an aggregate. The optimistic concurrency control
feature, and the compression and encryption features are also
demonstrated. We will use this test several times with different
configurations of persistence for our application object.

.. code-block:: python

    from eventsourcing.persistence import IntegrityError
    from eventsourcing.system import NotificationLogReader


    def test(app: Universe, expect_visible_in_db: bool):
        # Check app has zero event notifications.
        assert len(app.log['1,10'].items) == 0

        # Create a new aggregate.
        world_id = app.create_world('Earth')

        # Execute application commands.
        app.make_it_so(world_id, 'dinosaurs')
        app.make_it_so(world_id, 'trucks')

        # Check recorded state of the aggregate.
        assert app.get_history(world_id) == [
            'dinosaurs',
            'trucks'
        ]

        # Execute another command.
        app.make_it_so(world_id, 'internet')

        # Check recorded state of the aggregate.
        assert app.get_history(world_id) == [
            'dinosaurs',
            'trucks',
            'internet'
        ]

        # Check values are (or aren't visible) in the database.
        values = [b'dinosaurs', b'trucks', b'internet']
        if expect_visible_in_db:
            expected_num_visible = len(values)
        else:
            expected_num_visible = 0

        actual_num_visible = 0
        reader = NotificationLogReader(app.log)
        for notification in reader.read(start=1):
            for what in values:
                if what in notification.state:
                    actual_num_visible += 1
                    break
        assert expected_num_visible == actual_num_visible

        # Get historical state (at version 3, before 'internet' happened).
        old = app.repository.get(world_id, version=3)
        assert len(old.history) == 2
        assert old.history[-1] == 'trucks'  # last thing to have happened was 'trucks'

        # Check app has four event notifications.
        assert len(app.log['1,10'].items) == 4

        # Optimistic concurrency control (no branches).
        old.make_it_so('future')
        try:
            app.save(old)
        except IntegrityError:
            pass
        else:
            raise Exception("Shouldn't get here")

        # Check app still has only four event notifications.
        assert len(app.log['1,10'].items) == 4

        # Read event notifications.
        reader = NotificationLogReader(app.log)
        notifications = list(reader.read(start=1))
        assert len(notifications) == 4

        # Create eight more aggregate events.
        world_id = app.create_world('Mars')
        app.make_it_so(world_id, 'plants')
        app.make_it_so(world_id, 'fish')
        app.make_it_so(world_id, 'mammals')

        world_id = app.create_world('Venus')
        app.make_it_so(world_id, 'morning')
        app.make_it_so(world_id, 'afternoon')
        app.make_it_so(world_id, 'evening')

        # Get the new event notifications from the reader.
        last_id = notifications[-1].id
        notifications = list(reader.read(start=last_id + 1))
        assert len(notifications) == 8

        # Get all the event notifications from the application log.
        notifications = list(reader.read(start=1))
        assert len(notifications) == 12


Development environment
=======================

We can run the test in default "development" environment using
the default "plain old Python objects" infrastructure (which keeps
stored events in memory). The example below runs with no compression or
encryption of the stored events.

.. code-block:: python

    # Construct an application object.
    app = Universe()

    # Run the test.
    test(app, expect_visible_in_db=True)


SQLite environment
==================

You can configure a "production" environment to use an
`SQLite database <https://www.sqlite.org/>`__ for
storing event with the following environment variables.

Using the library's SQLite infrastructure will keep stored events in an.
The library's SQLite infrastructure is provided by the .

To use the library's :ref:`SQLite infrastructure <SQLite>`,
set ``INFRASTRUCTURE_FACTORY`` to the value ``"eventsourcing.sqlite:Factory"``.
When using the library's SQLite infrastructure, the environment variable
``SQLITE_DBNAME`` must also be set. This value will be passed to Python's
:func:`sqlite3.connect`.

.. code-block:: python

    import os


    # Use SQLite infrastructure.
    os.environ['INFRASTRUCTURE_FACTORY'] = 'eventsourcing.sqlite:Factory'

    # Configure SQLite database URI. Either use a file-based DB;
    os.environ['SQLITE_DBNAME'] = '/path/to/your/sqlite-db'
    # or use an in-memory DB with cache not shared, only works with single thread;
    os.environ['SQLITE_DBNAME'] = ':memory:'
    # or use an in-memory DB with shared cache, works with multiple threads;
    os.environ['SQLITE_DBNAME'] = ':memory:?mode=memory&cache=shared'
    # or use a named in-memory DB, allows distinct databases in same process.
    os.environ['SQLITE_DBNAME'] = 'file:application1?mode=memory&cache=shared'

    # Set optional lock timeout (default 5s).
    os.environ['SQLITE_LOCK_TIMEOUT'] = '10'  # seconds


Please note, a file-based SQLite database will have its journal mode set to use
write-ahead logging (WAL), which allows reading to proceed concurrently reading
and writing. Writing is serialised with a lock. The lock timeout can be adjusted
from the SQLite default of 5s by setting the environment variable `SQLITE_LOCK_TIMEOUT`.

Optionally, set the cipher key using environment variable `CIPHER_KEY` and select a
compressor by setting environment variable `COMPRESSOR_TOPIC`.

This example uses the Python `zlib` module to compress stored events, and AES
to encrypt the compressed stored events, before writing them to the SQLite database.
To use the library's encryption functionality, please install the library with the
`crypto` option (or just install the `pycryptodome` package.) To use an alternative
cipher strategy, set the environment variable `CIPHER_TOPIC`.

::

    $ pip install eventsourcing[crypto]


.. code-block:: python

    from eventsourcing.cipher import AESCipher

    # Generate a cipher key (keep this safe).
    cipher_key = AESCipher.create_key(num_bytes=32)

    # Cipher key.
    os.environ['CIPHER_KEY'] = cipher_key

    # Compressor topic.
    os.environ['COMPRESSOR_TOPIC'] = 'zlib'


Having configured the application with these environment variables, we
can construct the application and run the test using SQLite.

.. code-block:: python

    # Construct an application object.
    app = Universe()

    # Run the test.
    test(app, expect_visible_in_db=False)


PostgreSQL environment
======================

You can configure "production" environment to use the library's
PostgresSQL infrastructure with the following environment variables.
Using PostgresSQL infrastructure will keep stored events in a
PostgresSQL database. The PostgreSQL infrastructure is provided by
the :mod:`eventsourcing.postgres` module.

Please note, to use the library's PostgreSQL functionality,
please install the library with the `postgres` option (or just
install the `psycopg2` package.)

::

    $ pip install eventsourcing[postgres]

Please note, the library option `postgres_dev` will install the
`psycopg2-binary` which is much faster, but this is not recommended
for production use. The binary package is a practical choice for
development and testing but in production it is advised to use
the package built from sources.

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
    os.environ['INFRASTRUCTURE_FACTORY'] = 'eventsourcing.postgres:Factory'

    # Configure database connections.
    os.environ['POSTGRES_DBNAME'] = 'eventsourcing'
    os.environ['POSTGRES_HOST'] = '127.0.0.1'
    os.environ['POSTGRES_PORT'] = '5432'
    os.environ['POSTGRES_USER'] = 'eventsourcing'
    os.environ['POSTGRES_PASSWORD'] = 'eventsourcing'

    # Optional config.
    # - connection max age (connections stay open by default)
    os.environ['POSTGRES_CONN_MAX_AGE'] = '60'  # seconds
    # - check connection before use (pessimistic disconnect handling, default 'n')
    os.environ['POSTGRES_PRE_PING'] = 'y'
    # - timeout to wait for table lock when inserting (default no timeout)
    os.environ['POSTGRES_LOCK_TIMEOUT'] = '10'  # seconds
    # - timeout for sessions with idle transactions (default no timeout)
    os.environ['POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT'] = '10'  # seconds


Please note, to avoid interleaving of inserts when writing events, an
'EXCLUSIVE' mode table lock is acquired when using PostgreSQL. This
effectively serialises writing events. It prevents concurrent transactions
interleaving inserts, which would potentially cause notification log readers
that are tailing the application notification log to miss event notifications.
Reading from the table can proceed concurrently with other readers and writers,
since selecting acquires an 'ACCESS SHARE' lock which does not block and
is not blocked by the 'EXCLUSIVE' lock. This issue of interleaving inserts
by concurrent writers is not exhibited by SQLite, which supports concurrent
readers when its journal mode is set to use write ahead logging.

Having configured the application with these environment variables,
we can construct the application and run the test using PostgreSQL.


.. code-block:: python

    # Construct an application object.
    app = Universe()

    # Run the test.
    test(app, expect_visible_in_db=False)

