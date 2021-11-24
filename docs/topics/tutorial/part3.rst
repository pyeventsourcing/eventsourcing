================================
Tutorial - Part 3 - Applications
================================


As we saw in :doc:`Part 1 </topics/tutorial/part1>`, we can
use the library's ``Application`` class to define event-sourced
applications.

For example, the ``Universe`` application class, defined below, has a
command method ``create_world()`` that creates and saves a new ``World`` aggregate.
It has a command method ``make_it_so()`` that retrieves a previously saved
aggregate, calls ``make_it_so()`` on the aggregate, and then saves the
modified aggregate. And it has a query method ``get_history()`` that
retrieves and returns the ``history`` of an aggregate object. The
``World`` aggregate is used by the application.

.. code-block:: python

    from eventsourcing.application import Application
    from eventsourcing.domain import Aggregate, event


    class Universe(Application):
        def create_world(self, name):
            world = World(name)
            self.save(world)
            return world.id

        def make_it_so(self, world_id, what):
            world = self.repository.get(world_id)
            world.make_it_so(what)
            self.save(world)

        def get_history(self, world_id):
            world = self.repository.get(world_id)
            return world.history


    class World(Aggregate):
        @event('Started')
        def __init__(self, name):
            self.name = name
            self.history = []

        @event('SomethingHappened')
        def make_it_so(self, what):
            self.history.append(what)


We can construct an application object and call its methods.

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
    assert application.log
    assert application.log.recorder


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

**COMMENT**
This is the first time that the concept of notifications has been covered.  Speaking
from personal experience only, I found this a bit confusing reading the main docs:
how is a "notification" different from an "event"?  I'd be tempted to leave this until 
later.  The focus at the moment is how events are persisted, read, and aggregates re-created
from them.  
**END COMMENT**

In addition to these attributes, an application object has a method ``save()``
which is responsible for collecting new aggregate events and putting them in
the event store.  :doc:`Part 2 </topics/tutorial/part2>` of the tutorial explained
that events are generated each time a method is called on an aggregate object that is 
decorated with the ``@event`` decorator.  Those events are stored with the aggregate, and
can be retrieved using the ``collect_events()`` method.  The aggregates "event store" can be
thought of as a local cache of "pending events" .  The application ``save()`` method persists 
an aggregate's state by collecting and storing those pending aggregate events. The ``save()``
method calls the given aggregate's ``collect_events()`` method and
saves the pending aggregate events in the event store, with a
guarantee that either all of the events will be stored or none of
them will be.

**COMMENT**
1. What happens if none of the events are stored?  Do they remain in the aggregate's pending events
cache and get persisted next time ``save()`` is called?
1. What happens if ``save()`` is successful?  Are the events removed from the pending event cache?

Think the answers to both are "yes", probably worth clarifying.
**END COMMENT**

The repository has a ``get()`` method which is responsible
for reconstructing aggregates that have been previously saved.
The ``get()`` method is called with an aggregate ID. It retrieves
stored events for an aggregate from an event store, selecting them
using the given ID. It then reconstructs the aggregate object from its
previously stored events calling the ``mutate()`` method of aggregate
event objects, and returns the reconstructed aggregate object to
the caller.

A subclass of ``Application`` will usually define command and query methods which
make use of the application's ``save()`` method and the repository's
``get()`` method.

For example, the ``Universe`` class has ``create_world()`` and
``make_it_so()`` methods, both of which change the aggregate's state.
It also has a ``get_history()`` method, which is used to retrieve an aspect of
the aggregate's state.

`Domain-Driven Design <https://en.wikipedia.org/wiki/Domain-driven_design>`__ refers to these
as "command" and "query" methods respectively.  Let's explore those concepts. 


Command methods
===============

Let's consider the ``create_world()`` and ``make_it_so()`` methods
of the ``Universe`` application.

Firstly, let's create a new aggregate by calling the application method ``create_world()``.

.. code-block:: python

    world_id = application.create_world('Earth')

When the application command method ``create_world()``
is called, a new ``World`` aggregate object is created, by calling
the aggregate class. The new aggregate object is saved by calling
the application's ``save()`` method, and then the ID of the aggregate
is returned to the caller.

We can then evolve the state of the aggregate by calling the
application command method ``make_it_so()``.

.. code-block:: python

    application.make_it_so(world_id, 'dinosaurs')
    application.make_it_so(world_id, 'trucks')
    application.make_it_so(world_id, 'internet')

When the application command method ``make_it_so()`` is called with
the ID of an aggregate, the ``get()`` method of the ``repository`` is
used to get the aggregate, the aggregate's ``make_it_so()`` method is
called with the given value of ``what``, and the aggregate is then
saved by calling the application's ``save()`` method.

These are "commands" because they change the application state - either 
creating new aggregates (as in the case of ``create_world()``) or by modifying existing 
(as in the case of ``make_it_so()``).


Query methods
=============

We can access the state of the application's aggregate by calling the
application query method ``get_history()``.

.. code-block:: python

    history = application.get_history(world_id)
    assert history == ['dinosaurs', 'trucks', 'internet']


When the application query method ``get_history()`` is called with
the ID of an aggregate, the ``get()`` method of the ``repository``
is used to reconstruct the aggregate from saved events, and the value
of the aggregate's ``history`` attribute is returned to the caller.


Event notifications
===================

**COMMENT**
This section (up to "Application configuration") feels out of place here.  
So far, there's been no discussion of multi-application systems - and why multiple applications
might be useful/necessary.  Without that, I suspect the reader is lacking context and motivation:
why would I want to look at notifications? Total ordering sounds very nice, but why is it useful to
me?

Without that motivation, it's not clear why notifications are even relevant, never mind the finer 
details of dual writing, electing, etc.  I've had a go at introducing the concept though it's far 
from complete.  
**END COMMENT**

So far, we've discussed *events* as the means to record the evolution of each aggregate
over time. Simply by decorating the aggregate's command methods with ``@event`` and committing the 
changes to storage via the application's ``save()`` method, we get a fine-grained, ordered and complete record of 
all changes made to each aggregate.  That record can be seen as internal to the aggregate: a private, detailed account of 
its past.

An application will typically have more than one aggregate object.  
Each has its own life story, and evolves independently of its peers.  
Some systems have more than one application, where one needs to be aware of changes to another.  
Notifications provide that in an elegant, loosely coupled manner.  Whereas 
events are each aggregate's private record of its detailed evolution, notifications 
advertise those changes to the wider system.

The ``Application`` class has a ``log`` attribute,
which is a 'notification log' (aka the 'outbox pattern').

This pattern avoids the "dual writing" problem of recording
application state and separately sending messages about
the changes. Please note, it is equally important to avoid
"dual writing" in the consumption of event notifications.

The notification log can be used to propagate the state of
the application in a manner that supports deterministic
processing of it in event-driven systems.
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


Application configuration
=========================

**COMMENT**
I think this section would be better termed "Persistence configuration" - 
because that's what it covers.  There's probably also a case for it coming before 
"Command methods" - it's more of a natural flow on from the mechanics of how 
events are persisted to storage from the aggregate's pending events.
**END COMMENT**

An application object can be configured to use one
of many different ways of storing and retrieving events.

The application object can be configured using
:ref:`environment variables <Application environment>` to
work with different databases, and optionally to encrypt and compress
stored events. By default, the application serialises aggregate events
using JSON, and stores them in memory as "plain old Python objects".
The library also supports storing events in SQLite and PostgreSQL databases.
Other databases are available. See the library's 
`extension projects <https://github.com/pyeventsourcing>`__ 
for more information about what is currently supported.

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
To use the library's :ref:`SQLite infrastructure <SQLite>`,
set ``PERSISTENCE_MODULE`` to the value ``'eventsourcing.sqlite'``.
When using the library's SQLite infrastructure, the environment variable
``SQLITE_DBNAME`` must also be set. This value will be passed to Python's
:func:`sqlite3.connect`.

.. code-block:: python

    import os


    # Use SQLite infrastructure.
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
