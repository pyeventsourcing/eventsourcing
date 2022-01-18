================================
Tutorial - Part 3 - Applications
================================


As we saw in :doc:`Part 1 </topics/tutorial/part1>`, we can
use the library's ``Application`` class to define event-sourced
applications.

For example, the ``Universe`` application class, defined below, has a
command method ``register_dog()`` that creates and saves a new ``Dog`` aggregate.
It has a command method ``add_trick()`` that retrieves a previously saved
aggregate, calls ``add_trick()`` on the aggregate, and then saves the
modified aggregate. And it has a query method ``get_tricks()`` that
retrieves and returns the ``tricks`` of an aggregate object. The
``Dog`` aggregate is used by the application.

.. code-block:: python

    from eventsourcing.application import Application
    from eventsourcing.domain import Aggregate, event


    class Universe(Application):
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


We can construct an application object and call its methods.

.. code-block:: python

    application = Universe()

    dog_id = application.register_dog('Fido')
    application.add_trick(dog_id, 'roll over')
    application.add_trick(dog_id, 'fetch ball')
    application.add_trick(dog_id, 'play dead')

    history = application.get_tricks(dog_id)

    assert history == ['roll over', 'fetch ball', 'play dead']


Let's explore how this works in more detail.


Applications in more detail
===========================

An event-sourced application comprises many event-sourced aggregates,
and a persistence mechanism to store and retrieve aggregate events.
Constructing an application object constructs a persistence mechanism
the application will use to store and retrieve events. The construction
of the persistence mechanism can be easily configured, with
alternatives constructed instead of the standard defaults.

.. code-block:: python

    application = Universe()

    assert application.repository
    assert application.repository.event_store
    assert application.repository.event_store.mapper
    assert application.repository.event_store.mapper.transcoder
    assert application.repository.event_store.mapper.compressor is None
    assert application.repository.event_store.mapper.cipher is None
    assert application.repository.event_store.recorder
    assert application.notification_log
    assert application.notification_log.recorder


To be specific, an application object has a repository object. The repository
object has an event store. The event store object has a mapper. The mapper
object has a transcoder, an optional compressor, and an optional cipher. The
application also has a notification log. The notification log object
has a recorder.

The event store converts aggregate events to a common type of object called
"stored events", using the mapper, and then records the stored event objects
in the database using the recorder. The mapper uses the transcoder to serialize
aggregate events, and optionally to compress and encrypt the serialised state.
The recorder adapts a particular database, supporting the recording of stored events
in that database.

The repository reconstructs aggregate objects from aggregate event objects that
it retrieves from the event store. The event store gets stored events from the
recorder, and uses the mapper to reconstruct aggregate event objects. The mapper
uses the transcoder to optionally decrypt and decompress the serialised state,
and to deserialize stored events to aggregate events.

An application's recorder also puts the stored events in a total order, and allows
this order to be selected from. The notification log selects events from this order
as the event notifications of the application.

In addition to these attributes, an application object has a method ``save()``
which is responsible for collecting new aggregate events and putting them in
the event store.
The application ``save()`` method saves aggregates by
collecting and storing pending aggregate events. The ``save()``
method calls the given aggregates' ``collect_events()`` method and
puts the pending aggregate events in the event store, with a
guarantee that either all of the events will be stored or none of
them will be.

The repository has a ``get()`` method which is responsible
for reconstructing aggregates that have been previously saved.
The ``get()`` method is called with an aggregate ID. It retrieves
stored events for an aggregate from an event store, selecting them
using the given ID. It then reconstructs the aggregate object from its
previously stored events calling the ``mutate()`` method of aggregate
event objects, and returns the reconstructed aggregate object to
the caller.

In addition to these attributes and these methods, a subclass of
``Application`` will usually define command and query methods, which
make use of the application's ``save()`` method and the repository's
``get()`` method.

For example, the ``Universe`` class has a ``register_dog()`` method
and a ``add_trick()`` method, which can be considered a command methods.
It also has a ``get_tricks()`` method, which can be considered a query
method.


Command methods
===============

Let's consider the ``register_dog()`` and ``add_trick()`` methods
of the ``Universe`` application.

Firstly, let's create a new aggregate by calling the application method ``register_dog()``.

.. code-block:: python

    dog_id = application.register_dog('Fido')

When the application command method ``register_dog()``
is called, a new ``Dog`` aggregate object is created, by calling
the aggregate class. The new aggregate object is saved by calling
the application's ``save()`` method, and then the ID of the aggregate
is returned to the caller.

We can then evolve the state of the aggregate by calling the
application command method ``add_trick()``.

.. code-block:: python

    application.add_trick(dog_id, 'roll over')
    application.add_trick(dog_id, 'fetch ball')
    application.add_trick(dog_id, 'play dead')

When the application command method ``add_trick()`` is called with
the ID of an aggregate, the ``get()`` method of the ``repository`` is
used to get the aggregate, the aggregate's ``add_trick()`` method is
called with the given value of ``trick``, and the aggregate is then
saved by calling the application's ``save()`` method.


Query methods
=============

We can access the state of the application's aggregate by calling the
application query method ``get_tricks()``.

.. code-block:: python

    history = application.get_tricks(dog_id)
    assert history == ['roll over', 'fetch ball', 'play dead']


When the application query method ``get_tricks()`` is called with
the ID of an aggregate, the ``get()`` method of the ``repository``
is used to reconstruct the aggregate from saved events, and the value
of the aggregate's ``tricks`` attribute is returned to the caller.


Event notifications
===================

The ``Application`` class has a ``notification_log`` attribute,
which is a 'notification log' (aka the 'outbox pattern').
This pattern avoids the "dual writing" problem of recording
application state and separately sending messages about
the changes. Please note, it is equally important to avoid
"dual writing" in the consumption of event notifications.

The notification log can be used to propagate the state of
the application in a manner that supports deterministic
processing of the application state in event-driven systems.
It presents all the aggregate events that have been stored
across all the aggregates of an application as a sequence of
event notifications.

The log presents the aggregate events in the order in which
they were stored. Each of the event notifications has an integer
ID which increases along the sequence. An event notification is
simply a stored event (see above) that also has an ``id`` attribute.
Therefore, depending on the configuration of the application, it
may be already compressed and encrypted.

The ``select()`` method of the notification log can be used
to obtain a selection of the application's event notifications.
The argument ``start`` can be used to progressively read all
of a potentially very large number of event notifications.
The ``limit`` argument can be used to restrict the number
of event notifications that will be returned when the method
is called.

.. code-block:: python

    notifications = application.notification_log.select(start=1, limit=4)
    assert [n.id for n in notifications] == [1, 2, 3, 4]

    assert 'Dog.Started' in notifications[0].topic
    assert b'Fido' in notifications[0].state
    assert dog_id == notifications[0].originator_id

    assert 'Dog.TrickAdded' in notifications[1].topic
    assert b'roll over' in notifications[1].state
    assert dog_id == notifications[1].originator_id

    assert 'Dog.TrickAdded' in notifications[2].topic
    assert b'fetch ball' in notifications[2].state
    assert dog_id == notifications[2].originator_id

    assert 'Dog.TrickAdded' in notifications[3].topic
    assert b'play dead' in notifications[3].state
    assert dog_id == notifications[3].originator_id


Application configuration
=========================

An application object can be configured to use one
of many different ways of storing and retrieving events.

The application object can be configured using
:ref:`environment variables <Application environment>` to
work with different databases, and optionally to encrypt and compress
stored events. By default, the application serialises aggregate events
using JSON, and stores them in memory as "plain old Python objects".
The library also supports storing events in SQLite and PostgreSQL databases.
Other databases are available. See the library's extension
projects for more information about what is currently supported.

The ``test()`` function below demonstrates the example ``Universe``
application in more detail, by creating many aggregates in one
application, by reading event notifications from the application log,
by retrieving historical versions of an aggregate, and so on. The
optimistic concurrency control, and the compression and encryption
features are also demonstrated. The steps are commented for greater
readability. Below, the ``test()`` function is used several times
with different configurations of persistence for our application
object: with "plain old Python objects", with SQLite, and then
with PostgreSQL.

.. code-block:: python

    from eventsourcing.persistence import IntegrityError
    from eventsourcing.system import NotificationLogReader


    def test(app: Universe, expect_visible_in_db: bool):
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
        assert len(app.notification_log['1,10'].items) == 4

        # Optimistic concurrency control (no branches).
        old.add_trick('future')
        try:
            app.save(old)
        except IntegrityError:
            pass
        else:
            raise Exception("Shouldn't get here")

        # Check app still has only four event notifications.
        assert len(app.notification_log['1,10'].items) == 4

        # Read event notifications.
        reader = NotificationLogReader(app.notification_log)
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
    app = Universe()

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
    app = Universe()

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
    app = Universe()

    # Run the test.
    test(app, expect_visible_in_db=False)

In this example, stored events are both compressed and encrypted. In consequence,
we can expect the recorded values not to be visible in the database records.


Exercise
========

Follow the steps in this tutorial in your development environment.

Firstly, configure and run the application code you have written with
an SQLite database. Secondly, create a PostgreSQL database, and configure
and run your application with a PostgreSQL database. Connect to the databases
with the command line clients for SQLite and PostgreSQL, and examine the
database tables to verify that stored events have been recorded.


Next steps
==========

For more information about event-sourced aggregates, please read through
the :doc:`domain module documentation </topics/domain>`.
For more information about event-sourced applications, please read through
the :doc:`application module documentation </topics/application>`.
For more information about the persistence mechanism for event-sourced
applications, please read through the the
:doc:`persistence module documentation </topics/persistence>`.
