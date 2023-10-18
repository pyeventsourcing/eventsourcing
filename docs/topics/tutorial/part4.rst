===========================
Tutorial - Part 4 - Systems
===========================


As we saw in :doc:`Part 3 </topics/tutorial/part1>`, we can use the library's
:class:`~eventsourcing.application.Application` class to define event-sourced
applications. In this part, we will create two applications: the ``DogSchool``
application that we discussed in Part 3, and a second application which can pull
and process the domain events of the ``DogSchool`` application from its notification
log.

First, let's define the ``DogSchool`` application and the ``Dog`` aggregate.

.. code-block:: python

    from uuid import uuid5, NAMESPACE_URL

    from eventsourcing.application import Application
    from eventsourcing.domain import Aggregate, event


    class DogSchool(Application):
        def register_dog(self, name):
            dog = Dog(name)
            self.save(dog)
            return dog.id

        def add_trick(self, name, trick):
            dog = self.repository.get(Dog.create_id(name))
            dog.add_trick(trick=trick)
            self.save(dog)

        def get_dog(self, name):
            dog = self.repository.get(Dog.create_id(name))
            return {'name': dog.name, 'tricks': tuple(dog.tricks)}


    class Dog(Aggregate):
        @event('Registered')
        def __init__(self, name):
            self.name = name
            self.tricks = []

        @classmethod
        def create_id(cls, name):
            return uuid5(NAMESPACE_URL, f'/dogs/{name}')

        @event('TrickAdded')
        def add_trick(self, trick):
            self.tricks.append(trick)



Process applications
====================

Second, let's define an application which can pull and process the domain events
of the ``DogSchool`` application from its notification log. The ``Counters`` class
below is an event processing application. It extends the library's
:class:`~eventsourcing.system.ProcessApplication` class.

The most important thing that needs to be defined when processing domain events is
a policy function.

The policy function defines how individual domain events will be processed. A policy
function has different responses for different types of domain events. The policy function
may create changes to the state of the event processing application. These could be
changes to an event-sourced domain model, or they could be updates to a non-event sourced
materialized view. In this example, we will make changes to an event-sourced domain
model.

In the example below, the ``Counters`` application counts the tricks added
in the ``Dog`` aggregates. It has a ``policy()`` function that processes the
``Dog.TrickAdded`` events of the ``DogSchool`` application. It makes changes to an
event-sourced domain model comprised of ``Counter`` aggregates.

The ``Counter`` aggregate class has a ``name`` which will correspond to the name of a trick.
It also has a ``count`` attribute, which is an integer value with an initial value of ``0``. It
also has an ``increment()`` method, decorated with the :func:`@event<eventsourcing.domain.event>`
decorator, which increments the value of its ``count`` attribute.

When a ``Dog.TrickAdded`` event is processed by the ``policy()`` function of the ``Counters`` application,
the name of the trick is used to get or create a ``Counter`` aggregate object. Then, the counter's
``increment()`` method is called once. The new domain events are then collected on a "processing event"
object before the policy function returns.

The ``policy()`` function receives two arguments: ``domain_event`` and ``process_event``. The ``domain_event``
argument is a domain event object that is to be processed. The ``process_event`` is an instance of the
:class:`~eventsourcing.application.ProcessingEvent` class. New domain events created in the
policy function are collected by calling the process event object's
:func:`~eventsourcing.application.ProcessingEvent.collect_events` method.

The purpose of the process event object is to hold all the new domain events created by the policy function, along
with a :class:`~eventsourcing.persistence.Tracking` object that indicates a position in an application sequence
of the domain event that is being processed. These factors will be recorded together atomically by the process
application after the policy function returns. The tracking records are used to avoid dual writing in the
consumption and processing of domain events, so that each domain event is processed exactly once.

.. code-block:: python

    from eventsourcing.application import AggregateNotFound
    from eventsourcing.system import ProcessApplication
    from eventsourcing.dispatch import singledispatchmethod


    class Counters(ProcessApplication):
        @singledispatchmethod
        def policy(self, domain_event, process_event):
            """Default policy"""

        @policy.register(Dog.TrickAdded)
        def _(self, domain_event, process_event):
            trick = domain_event.trick
            try:
                counter_id = Counter.create_id(trick)
                counter = self.repository.get(counter_id)
            except AggregateNotFound:
                counter = Counter(trick)
            counter.increment()
            process_event.collect_events(counter)

        def get_count(self, trick):
            counter_id = Counter.create_id(trick)
            try:
                counter = self.repository.get(counter_id)
            except AggregateNotFound:
                return 0
            return counter.count


    class Counter(Aggregate):
        def __init__(self, name):
            self.name = name
            self.count = 0

        @classmethod
        def create_id(cls, name):
            return uuid5(NAMESPACE_URL, f'/counters/{name}')

        @event('Incremented')
        def increment(self):
            self.count += 1


Defining an event-driven system
===============================

Just like an application can be defined independently of concrete persistence infrastructure, we can
define which applications "follow" which other applications independently of the manner in which domain
events are pulled and processed. For this purpose, we can use the library's
:class:`~eventsourcing.system.System` class to specify a list of "pipes".

In the example below, we define a system with one "pipe" that has the ``DogSchool`` application
followed by the ``Counters`` application.

.. code-block:: python

    from eventsourcing.system import System

    system = System(pipes=[[DogSchool, Counters]])


The system object builds a graph of the application classes, identifying "nodes" and "edges".

.. code-block:: python

    assert list(system.nodes) == ['DogSchool', 'Counters'], list(system.nodes)
    assert system.edges == [('DogSchool', 'Counters')], system.edges


When the system is run, the nodes will be instantiated as application objects, and the edges
will be used to set up the applications to "lead" and "follow" each other. Exactly how depends
upon the concrete implementation of a system runner.


Runnning an event-driven system
===============================

Just like it's possible to store events in different ways, it's possible to run an event-driven system
in different ways. There are many possibilities for the orchestration of the applications in a system
and for interprocess communication between the applications. One possibility is to use a single thread,
and to pull and process events synchronously and sequentially. Another possibility is to use multiple
threads in the same operating system process, with events processed concurrently and asynchronously.
If the application objects are all constructed in the same operating system process, the notification
logs can be used directly.

Another possibility is to use multiple operating system processes on the same machine, or alternatively
on different machines in a network. When running a system with multiple operating system
processes, their notification logs must be accessed remotely across the operating system
process boundary. There are many possible alternatives for inter-process communication,
by which events are transported from one application to another.

The important thing, in all these cases, is to pull and process a sequence of events, and for new
state in the downstream application to be recorded atomically along with a unique tracking record
that indicates the position in the upstream sequence. And, when resuming the processing of events,
to use the last recorded position in the downstream application to pull subsequent events from the
upstream application. To demonstrate how this works, this library provides a
:class:`~eventsourcing.system.SingleThreadedRunner` and a :class:`~eventsourcing.system.MultiThreadedRunner`.

The :class:`~eventsourcing.system.SingleThreadedRunner` and :class:`~eventsourcing.system.MultiThreadedRunner`
classes implement the abstract :class:`~eventsourcing.system.Runner` class. These system runners are constructed
with an instance of the :class:`~eventsourcing.system.System` class, and optionally an ``env`` dictionary.

The runners have a :func:`~eventsourcing.system.Runner.start` method which constructs and connects the
applications. The runners also have a :func:`~eventsourcing.system.Runner.get` method, which returns an
application. When application command methods are called, new events will be propagated and processed,
according to the system definition and the application policies. Application query methods can be used
to obtain the resulting state of the system.

The ``test()`` function below shows how the abstract runner interface can be used to operate the dog school
trick counting system.

We will run the ``test()`` function firstly with the :class:`~eventsourcing.system.SingleThreadedRunner` and
then the :class:`~eventsourcing.system.MultiThreadedRunner`. The applications will use the POPO persistence
module by default. We will then run the test again, with the library's SQLite persistence module, and then
with the PostgreSQL persistence module.

.. code-block:: python

    from time import sleep

    def test(system, runner_class, wait=0, env=None):

        # Start running the system.
        runner = runner_class(system, env=env)
        runner.start()

        # Get the application objects.
        school = runner.get(DogSchool)
        counters = runner.get(Counters)

        # Generate some events.
        school.register_dog('Billy')
        school.register_dog('Milly')
        school.register_dog('Scrappy')

        school.add_trick('Billy', 'roll over')
        school.add_trick('Milly', 'roll over')
        school.add_trick('Scrappy', 'roll over')

        # Wait in case events are processed asynchronously.
        sleep(wait)

        # Check the results of processing the events.
        assert counters.get_count('roll over') == 3
        assert counters.get_count('fetch ball') == 0
        assert counters.get_count('play dead') == 0

        # Generate more events.
        school.add_trick('Billy', 'fetch ball')
        school.add_trick('Milly', 'fetch ball')

        # Check the results.
        sleep(wait)
        assert counters.get_count('roll over') == 3
        assert counters.get_count('fetch ball') == 2
        assert counters.get_count('play dead') == 0

        # Generate more events.
        school.add_trick('Billy', 'play dead')

        # Check the results.
        sleep(wait)
        assert counters.get_count('roll over') == 3
        assert counters.get_count('fetch ball') == 2
        assert counters.get_count('play dead') == 1

        # Stop the runner.
        runner.stop()


Single-threaded runner
======================

We can run the system with the :class:`~eventsourcing.system.SingleThreadedRunner`.

.. code-block:: python

    from eventsourcing.system import SingleThreadedRunner

    test(system, SingleThreadedRunner)

When the events are processed synchronously, we do not need to ``wait`` for the results,
because the events will have been processed before the application command returns.

The applications will use the default POPO persistence module, because the environment variable
``PERSISTENCE_MODULE`` has not been set.

Multi-threaded runner
=====================

We can also run the system with the :class:`~eventsourcing.system.MultiThreadedRunner`. Because
the events are processed asynchronously, we need to ``wait`` for the results.

.. code-block:: python

    from eventsourcing.system import MultiThreadedRunner

    test(system, MultiThreadedRunner, wait=0.1)

Again, the applications will use the default POPO persistence module, because the environment variable
``PERSISTENCE_MODULE`` has not been set.


SQLite environment
==================

We can also run the system of applications with the library's SQLite persistence module.
In the example below, the applications use in-memory SQLite databases.

.. code-block:: python

    import os


    # Use SQLite for persistence.
    os.environ['PERSISTENCE_MODULE'] = 'eventsourcing.sqlite'

    # Use a separate in-memory database for each application.
    os.environ['SQLITE_DBNAME'] = ':memory:'

    # Run the system tests.
    test(system, SingleThreadedRunner)

When the events are processed synchronously, we do not need to ``wait`` for the results,
because the events will have been processed before the application command returns.

When running the system with the multi-threaded runner and SQLite databases, we need to be
careful to use separate databases for each application. We could use a file-based
database, but here we will use in-memory SQLite databases. Because we need SQLite's in-memory
databases to support multi-threading, we need to enable SQLite's shared cache. Because we
need to enable the shared cache, and we need more than one database in the same operating
system process, we also need to use named in-memory databases. The SQLite URI pattern
``'file:{NAME}?mode=memory&cache=shared'`` specifies a named in-memory database that has a shared cache.
In order to distinguish environment variables for different applications in a system, the environment
variable names should be prefixed with the application name.

.. code-block:: python

    # Use separate named in-memory databases in shared cache.
    os.environ['DOGSCHOOL_SQLITE_DBNAME'] = 'file:dogschool?mode=memory&cache=shared'
    os.environ['COUNTERS_SQLITE_DBNAME'] = 'file:counters?mode=memory&cache=shared'

    # Run the system tests.
    test(system, MultiThreadedRunner, wait=0.2)


When the events are processed asynchronously, we need to ``wait`` for the results.

PostgreSQL Environment
======================

We can also run the system with the library's PostgreSQL persistence module. Just for fun,
we will also configure the system to compress and encrypt the domain events.

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

    test(system, SingleThreadedRunner)


Although we must use different SQLite databases for different applications, we can use the same PostgreSQL
database, because the PostreSQL persistence module creates separate tables for each application.

However, before running the test again with PostgreSQL, we need to reset the trick counts,
because they are being stored in a durable database and so would simply accumulate. We can
do this by deleting the database tables for the system.

.. code-block:: python

    from eventsourcing.postgres import PostgresDatastore
    from eventsourcing.tests.postgres_utils import drop_postgres_table

    db = PostgresDatastore(
        'eventsourcing',
        '127.0.0.1',
        '5432',
        'eventsourcing',
        'eventsourcing',
    )
    drop_postgres_table(db, 'dogschool_events')
    drop_postgres_table(db, 'counters_events')
    drop_postgres_table(db, 'counters_tracking')

After resetting the recorded state of the system, we can run the system again with the multi-threaded runner.

.. code-block:: python

    test(system, MultiThreadedRunner, wait=0.2)


When the state of the system is recorded in a durable database, we can access the
state of the system's applications by directly constructing the application objects.

.. code-block:: python

    assert DogSchool().get_dog('Scrappy')['tricks'] == ('roll over',)
    assert Counters().get_count('roll over') == 3


Exercise
========

Firstly, replicate the code in this tutorial in your development environment.

* Copy the code snippets above.
* Run the code with the default "plain old Python object"
  persistence module.
* Configure and run the system with an SQLite database.
* Create a PostgreSQL database, and configure and run the
  system with a PostgreSQL database.
* Connect to the databases with the command line clients for
  SQLite and PostgreSQL, and examine the database tables to
  observe the stored event records and the tracking records.

Secondly, write an system that...

Next steps
==========

* For more information about event-driven systems, please read
  :doc:`the system module documentation </topics/system>`.
* See also the :ref:`Example systems`.
