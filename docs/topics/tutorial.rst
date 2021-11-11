========
Tutorial
========

A tutorial for event sourcing in Python.

Python object classes
=====================

This tutorial depends on a basic understanding of
`Python classes <https://docs.python.org/3/tutorial/classes.html>`__.

For example, using Python we can define a ``World`` class as follows.

.. code-block:: python

    class World:
        def __init__(self, name):
            self.name = name
            self.history = []

        def make_it_so(self, what):
            self.history.append(what)

We can see, from the definition of the ``__init__()`` method,
that the attributes ``name`` and ``history`` will be initialised
when the ``World`` class is instantiated. We can also see that
instances of ``World`` will have a method ``make_it_so()``,
which appends the given value of its ``what`` argument to the
``history`` of an instance.

Having defined a Python class, we can use it to create an instance.

.. code-block:: python

    world = World('Earth')


As we might expect, the `world` object is an instance of the ``World`` class.

.. code-block:: python

    assert isinstance(world, World)


And so, the `world` object has a ``name`` attribute, which has
the value that was given when we called the ``World`` class object.

.. code-block:: python

    assert world.name == 'Earth'


The `world` object also has a ``history`` attribute, which is initially an empty list.

.. code-block:: python

    assert world.history == []


We can call the ``make_it_so()`` method on the `world` object.

.. code-block:: python

    world.make_it_so('Python')


The `world` object's ``history`` attribute will then have one item, which is the value
given when calling ``make_it_so()``.

.. code-block:: python

    assert world.history == ['Python']

This is a basic example of how Python classes work.

However, if we want to use this object in future, we will want,
somehow, to be able to save and to reconstruct it. That is, we
will want it to be "persistent".

It happens that a persistent object that changes through a sequence
of individual decisions corresponds to the notion 'aggregate' in
Domain-Driven Design. And an 'event-sourced' aggregate is persisted
by persisting the sequence of individual decisions that makes the
aggregate what it is as a sequence of 'event' objects. In this simple
example, the sequence is: a "world was created" and then "Python happened".

We can easily convert the example Python class above into a fully-functioning
event-sourced aggregate by using this library's ``Aggregate`` class and its
``@event`` `function decorator <https://docs.python.org/3/glossary.html#term-decorator>`__.
An event-sourced application comprises many event-sourced aggregates, and
a mechanism to store and retrieve aggregate events.


Event sourcing in Python
========================

We can use the aggregate base class ``Aggregate`` and the decorator
``@event`` from the :mod:`eventsourcing.domain` module to define
event-sourced aggregates in Python.


.. code-block:: python

    from eventsourcing.domain import Aggregate, event

We can also use the application base class ``Application`` from the
:mod:`eventsourcing.appliation` module to define event-sourced applications
in Python.

.. code-block:: python

    from eventsourcing.application import Application


Event-sourced aggregate
-----------------------

An event-sourced aggregate constructs, and its state is determined by, a sequence of events.

Let's convert the ``World`` class above into an event-sourced aggregate.
We can define an event-sourced ``World`` class by inheriting from ``Aggregate``.
We can use the ``@event`` decorator on command methods to define aggregate events.
The changes are highlighted below.

.. code-block:: python
    :emphasize-lines: 1,2,7

    class World(Aggregate):
        @event('Created')
        def __init__(self, name: str) -> None:
            self.name = name
            self.history = []

        @event('SomethingHappened')
        def make_it_so(self, what: str) -> None:
            self.history.append(what)


As before, we can call the aggregate class to create a new aggregate object.

.. code-block:: python

    world = World('Earth')

The `world` object is an instance of the ``World`` class. It is also an aggregate.

.. code-block:: python

    assert isinstance(world, World)
    assert isinstance(world, Aggregate)

As we might expect, the attributes ``name`` and ``history`` have been initialised.

.. code-block:: python

    assert world.name == 'Earth'
    assert world.history == []


The ``World`` aggregate object also has an ``id`` attribute. This follows from the default
behaviour of the ``Aggregate`` base class. It happens to be a version 4 (random) UUID.

.. code-block:: python

    from uuid import UUID

    assert isinstance(world.id, UUID)


As before, we can call the aggregate method ``make_it_so()``.

.. code-block:: python

    world.make_it_so('Python')

Calling the command method changes the state of the aggregate.

.. code-block:: python

    assert world.history == ['Python']

This time, we can also get event objects by calling the method ``collect_events()``.

.. code-block:: python

    events = world.collect_events()

And we can also reconstruct the aggregate by calling ``mutate()`` on the event objects.

.. code-block:: python

    copy = events[0].mutate(None)
    copy = events[1].mutate(copy)
    assert copy == world


By redefining the ``World`` class as an event-sourced aggregate in this way,
normal interactions with a Python object will construct a sequence of event
objects that we can save and to use to reconstruct the object. Interactions
with aggregates usually happen inside an application.


Event-sourced application
-------------------------

An event-sourced application is an application that interacts with event-sourced aggregates.

Let's define a ``Universe`` application that interacts with ``World`` aggregates.
We can define an event-sourced application with this library's ``Application``
base class. We can add command methods (to create and update aggregates)
and query methods (to view current state).

.. code-block:: python

    from typing import Tuple


    class Universe(Application):
        def create_world(self, name: str) -> UUID:
            world = World(name)
            self.save(world)
            return world.id

        def make_it_so(self, world_id: UUID, what: str) -> None:
            world = self._get_world(world_id)
            world.make_it_so(what)
            self.save(world)

        def get_history(self, world_id) -> Tuple:
            return self._get_world(world_id).history

        def _get_world(self, world_id) -> World:
            world = self.repository.get(world_id)
            assert isinstance(world, World)
            return world

We can collect and record aggregate events within application command methods by
using the application ``save()`` method. And we can use the repository ``get()``
method to retrieve and reconstruct aggregates from previously recorded events.


We can construct an instance of the application by calling the application class.

.. code-block:: python

    application = Universe()


We can then create and update the aggregates of the application by calling the
application command methods.

.. code-block:: python

    world_id = application.create_world('Earth')
    application.make_it_so(world_id, 'dinosaurs')
    application.make_it_so(world_id, 'trucks')
    application.make_it_so(world_id, 'internet')


We can also view the current state of the application by calling the application
query method.

.. code-block:: python

    history = application.get_history(world_id)
    assert history == ['dinosaurs', 'trucks', 'internet']

Any number of different kinds of event-sourced applications can
be defined in this way.

You can try this for yourself by copying the code snippets above.

Aggregates in more detail
=========================

Next, let's look at how all this works in more detail.

As we saw above, we can use the library's ``Aggregate`` class to define
event-sourced aggregates. Let's go through this more slowly.

Firstly, let's define the simplest possible event-sourced aggregate, by
simply subclassing the ``Aggregate`` class.

.. code-block:: python

    class World(Aggregate):
        pass


In the usual way with Python classes, we can create a new instance by
calling the class object.

.. code-block:: python

    world = World()
    assert isinstance(world, World)


The result is the same as a normal Python class. The difference is that
rather than having Python construct and initialise the aggregate instance,
when the aggregate class is called, the call is handled by the library.
An event object is constructed, and this event object is used to construct
and initialise the aggregate object. The point being, that same event object
can be used again in future to reconstruct the aggregate object.

But we can only do that if we have the new event object. Fortunately, the new
event object is not lost. It is held by the aggregate in an internal list. We
can collect the event object from our aggregate by calling the aggregate's
``collect_events()`` method, which is kindly provided by the aggregate base class.

.. code-block:: python

    events = world.collect_events()
    assert len(events) == 1

The "created" event object can be used to reconstruct the aggregate
object. To reconstruct the aggregate object, we can simply call the
event object's ``mutate()`` method.

.. code-block:: python

    copy = events[0].mutate(None)
    assert copy == world

Using events to determine the state of an aggregate is the essence of
event sourcing. Calling the event's ``mutate()`` method is exactly how
the aggregate object was constructed when the aggregate class was called.

You can try this for yourself by copying the code snippets above.

Next, let's talk about aggregate events in more detail.

Aggregate events in more detail
===============================

When the aggregate class code was
interpreted by Python, a "created" event class was automatically defined
on the aggregate class object. The name of the "created" event class was
given the default name "Created".

.. code-block:: python

    assert isinstance(World.Created, type)

The event we collected from the aggregate is an instance of this class.

.. code-block:: python

    assert isinstance(events[0], World.Created)

We can specify an aggregate event class by decorating an aggregate method
with the ``@event`` decorator. The event specified by the decorator will
be triggered when the decorated method is called. This happens by default
for the ``__init__()`` method. But we can also decorate an ``__init__()``
method to specify the name of the "created" event.

Let's redefine the event-sourced aggregate above, using the
``@event`` decorator on an ``__init__()`` method so that we can specify the
name of the "created" event.
Let's also define the ``__init__()`` method so that it accepts a ``name``
argument and initialises a ``name`` attribute with the given value of the argument.
The changes are highlighted below.

.. code-block:: python
  :emphasize-lines: 2-4

    class World(Aggregate):
        @event('Started')
        def __init__(self, name: str) -> None:
            self.name = name


By specifying the name of the "created" event to be ``'Started'``, an event
class with this name is defined on the aggregate class.

.. code-block:: python

    assert isinstance(World.Started, type)


We can call such events "created" events. They are the initial
event in the aggregate's sequence of aggregate events. The inherit the base
class "created" event, which has a method ``mutate()`` that knows how to
construct and initialise aggregate objects.

.. code-block:: python

    assert issubclass(World.Started, Aggregate.Created)

This general occurrence, of creating aggregate objects, needs a general
name. The name "created" is used for this purpose. We will need to
think of suitable names for the particular aggregate events we will
define in our domain models, but sadly the library can't us help with
that.

Again, as above, we can create a new aggregate instance by calling
the aggregate class. But this time, we need to provide a value for
the ``name`` argument.

.. code-block:: python

    world = World('Earth')


As we might expect, the given ``name`` is used to initialise the ``name``
attribute of the aggregate.

.. code-block:: python

    assert world.name == 'Earth'


We can call ``collect_events()`` to get the "created" event from
the aggregate object. We can see the event object is an instance of
the class ``World.Started``.

.. code-block:: python

    events = world.collect_events()
    assert isinstance(events[0], World.Started)


The attributes of an event class specified by using the ``@event`` decorator
are derived from the signature of the decorated method. Hence, the event
object has a ``name`` attribute, which follows from the signature of the
aggregate's ``__init__()`` method.

.. code-block:: python

    assert events[0].name == 'Earth'


We can take this further by defining a second method that will be used
to change the aggregate object after it has been created.

Let's firstly adjust the ``__init__()`` to initialise a ``history``
attribute with an empty list. Then let's also define a ``make_it_so()``
method that appends to this list, and decorate this method with
the ``@event`` decorator. The changes are highlighted below.

.. code-block:: python
    :emphasize-lines: 8,10-12

    from eventsourcing.domain import Aggregate, event


    class World(Aggregate):
        @event('Started')
        def __init__(self, name: str) -> None:
            self.name = name
            self.history = []

        @event('SomethingHappened')
        def make_it_so(self, what: str) -> None:
            self.history.append(what)


By decorating the ``make_it_so()`` method with the ``@event`` decorator,
an event class ``SomethingHappened`` was automatically defined on the
aggregate class.

.. code-block:: python

    assert isinstance(World.SomethingHappened, type)

The event will be triggered when the method is called. The
body of the method will be used by the event to mutate the
state of the aggregate object.

Let's create an aggregate instance.

.. code-block:: python

    world = World('Earth')

As we might expect, the ``name`` of the aggregate object is ``'Earth``,
and the ``history`` attribute is an empty list.

.. code-block:: python

    assert world.name == 'Earth'
    assert world.history == []

Now let's call ``make_it_so()`` method, with the value ``'Python'``.

.. code-block:: python

    world.make_it_so('Python')


The ``history`` list now has one item, ``'Python'``,
the value we passed when calling ``make_it_so()``.

.. code-block:: python

    assert world.history == ['Python']

Creating and updating the aggregate caused two events to occur,
a "started" event and a "something happened" event. We can collect
the events by calling ``collect_events()``.

.. code-block:: python

    events = world.collect_events()
    assert len(events) == 2

    assert isinstance(events[0], World.Started)
    assert isinstance(events[1], World.SomethingHappened)

Just like the "started" event has a ``name`` attribute, so the
"something happened" event has a ``what`` attribute.

.. code-block:: python

    assert events[0].name == 'Earth'
    assert events[1].what == 'Python'

This follows from the signatures of the ``__init__()`` and
the ``make_it_so()`` methods.

The arguments of a method decorated with ``@event`` are used to define
the attributes of an event class. When the method is called, the values
of the method arguments are used to construct an event object. The method
body is then executed with the attributes of the event. The result is the
same as if the method was not decorated. The difference is that a sequence
of events is generated. The point being, this sequence of events can be
used in future to reconstruct the current state of the aggregate.

.. code-block:: python

    copy = None
    for event in events:
        copy = event.mutate(copy)

    assert copy == world

Calling the aggregate's ``collect_events()`` method is what happens when
an application's ``save()`` method is called. Calling the ``mutate()``
methods of saved events' is how an application repository reconstructs
aggregates from saved events when its ``get()`` is called.


Applications in more detail
===========================

An "application" object in this library roughly corresponds to a "bounded context"
in Domain-Driven Design. An application can have aggregates of different types in
its domain model.

As we saw in the example above, we can construct an application object by calling
an application class. The example above defines an event-sourced application named
``Universe``. The application class ``Universe`` uses the application base class
``Application``. When the ``Universe`` application class is called, an application
object is constructed.

.. code-block:: python

    application = Universe()

As we have seen, the ``Universe`` application class has a command method ``create_world()``
that creates and saves new instances of the aggregate class ``World``. It has a
command method ``make_it_so()`` that calls the aggregate command method
``make_it_so()`` of an already existing aggregate object. And it
has a query method ``get_history()`` that returns the ``history`` of
an aggregate object.

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


We can cccess the state of the application's aggregate by calling the
application query method ``get_history()``.

.. code-block:: python

    history = application.get_history(world_id)
    assert history == ['dinosaurs', 'trucks', 'internet']


When the application query method ``get_history()`` is called with
the ID of an aggregate, the repository is used to get the
aggregate, and the value of the aggregate's ``history`` attribute
is returned to the caller.

How does it work? The ``Application`` class provides persistence
infrastructure that can collect, serialise, and store aggregate
events. It can also reconstruct aggregates from stored events.

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
the caller. The application class can be configured using
environment variables to work with different databases, and
optionally to encrypt and compress stored events. By default,
the application serialises aggregate events using JSON, and
stores them in memory as "plain old Python objects". The library
includes support for storing events in SQLite and PosgreSQL (see
below). Other databases are available.

The ``Application`` class also has a ``log`` object which can be
used to get all the aggregate events that have been stored
across all the aggregates of an application. The log presents
the aggregate events in the order in which they were stored,
as a sequence of event notifications. Each of the event
notifications has an integer ID which increases along the
sequence. The ``log`` can be used to propagate the state of
the application in a manner that supports deterministic
processing of the application state in event-driven systems.


.. code-block:: python

    log_section = application.log['1,4']
    notifications = log_section.items
    assert [n.id for n in notifications] == [1, 2, 3, 4]

    assert 'World.Started' in notifications[0].topic
    assert 'World.SomethingHappened' in notifications[1].topic
    assert 'World.SomethingHappened' in notifications[2].topic
    assert 'World.SomethingHappened' in notifications[3].topic

    assert b'Earth' in notifications[0].state
    assert b'dinosaurs' in notifications[1].state
    assert b'trucks' in notifications[2].state
    assert b'internet' in notifications[3].state

    assert world_id == notifications[0].originator_id
    assert world_id == notifications[1].originator_id
    assert world_id == notifications[2].originator_id
    assert world_id == notifications[3].originator_id


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
configurations of our application object.

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


This example can be adjusted and extended for any event-sourced application.


Development environment
=======================

We can run the code in default "development" environment using
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


Project structure
=================

You are free to structure your project files however you wish. You
may wish to put your aggregate classes in a file named
``domainmodel.py`` and your application class in a file named
``application.py``.

::

    myproject/
    myproject/application.py
    myproject/domainmodel.py
    myproject/tests.py

But you can start by first writing a failing test in ``tests.py``, then define
your application and aggregate classes in the test module, and then refactor
by moving things to separate Python modules. You can also convert these modules
to packages if you want to break things up into smaller modules.
