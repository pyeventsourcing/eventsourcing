===========================
Tutorial - Part 4 - Systems
===========================


As we saw in :doc:`Part 3 </topics/tutorial/part1>`, we can use the library's
:class:`~eventsourcing.application.Application` class to define event-sourced
applications. In this part, we will create a second event-driven application which
pulls and processes event notifications from the notification log of the ``DogSchool``
application.

First, let's define the ``DogSchool`` application and the ``Dog`` aggregate.

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



Process applications
====================

The most important thing that needs to be defined when processing events is a policy function.
The policy function defines how individual events will be processed. The policy function creates
changes to the state of the process application. A policy function has different responses for
different types of events.

For example, we can define a policy that processes the ``Dog.TrickAdded`` events of the ``DogSchool``
application, so that we can count the number of tricks that have been added.

The ``Counters`` class below extends the ``ProcessApplication`` class by implementing a ``policy()``
function. The event-sourced aggregate ``Counter`` has a method ``increment()`` which increments the
count for a particular trick. When a ``Dog.TrickAdded`` event is processed, the ``increment()`` method
is called.

New events created in the policy function are collected by the ``process_event`` that is passed into
the ``policy()`` function along with the ``domain_event``. This ensures that all new events created
by a policy function in responding to an upstream domain event will be recorded atomically along with
a tracking record that indicates the position of the event in the upstream sequence of the domain event
that has been processed.

.. code-block:: python

    from uuid import uuid5, NAMESPACE_URL
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

Rather than manually constructing the applications and pulling and processing events, we can use
the library's :class:`~eventsourcing.system.System` class to indicate which application is the
"leader" and which is the "follower". In this way, just like the persistence infrastructure that
each application will use can be defined when the applications are constructed, also the manner
in which the events will be pulled and processed can be defined when the system is run.

.. code-block:: python

    from eventsourcing.system import System

    system = System(pipes=[[DogSchool, Counters]])


Runnning an event-driven system
===============================

Just like it's possible to store events in different ways, it's possible to run an event-driven system
in different ways. There are many possibilities for the orchestration of the applications in a system
and for interprocess communication between the applications. One possibility is to use a single thread,
and pull and process events sequentially. Another possibility is to use multiple threads in the same
operating system process, with events processed concurrently and asynchronously. Another possibility is
to use multiple operating system processes on the same machine, or alternatively on different machines
in a network. Furthermore, when running a system with multiple operating system processes, there are
many possible alternatives for inter-process communication by which events are transported from one
application to another.

The important thing, in all these cases, is to pull and process a sequence of events, and for new
state in the downstream application to be recorded atomically along with a unique tracking record
that indicates the position in the upstream sequence. And, when resuming the processing of events,
to use the last recorded position in the downstream application to pull subsequent events from the
upstream application. To demonstrate how this works, this library provides a
:class:`~eventsourcing.system.SingleThreadedRunner` and a :class:`~eventsourcing.system.MultiThreadedRunner`.

The :class:`~eventsourcing.system.SingleThreadedRunner` and a :class:`~eventsourcing.system.MultiThreadedRunner`
implement the abstract :class:`~eventsourcing.system.Runner` class. These system runners are constructed
with an instance of the :class:`~eventsourcing.system.System` class, and optionally an ``env`` dictionary.

The runners have a :func:`~eventsourcing.system.Runner.start`` method which constructs and connects the
applications. The runners also have a :func:`~eventsourcing.system.Runner.get`` method, which returns an
application. When application command methods are called, new events will be propagated and processed,
according to the system definition and the application policies. Application query methods can be used
to obtain the resulting state of the system.

The ``test()`` function below shows how the abstract runner interface can be used to operate the dog school
trick counting system. We will call the ``test()`` function firstly with the
:class:`~eventsourcing.system.SingleThreadedRunner` and then the :class:`~eventsourcing.system.MultiThreadedRunner`.
The applications will use the POPO persistence module by default. We will then run the system with the
library's SQLite persistence module, and then the PosgreSQL persistence module.

.. code-block:: python

    from time import sleep

    def test(system, runner_class, wait=0, env=None):

        runner = runner_class(system, env=env)
        runner.start()

        school = runner.get(DogSchool)
        counters = runner.get(Counters)

        dog_id1 = school.register_dog('Billy')
        dog_id2 = school.register_dog('Milly')
        dog_id3 = school.register_dog('Scrappy')

        school.add_trick(dog_id1, 'roll over')
        school.add_trick(dog_id2, 'roll over')
        school.add_trick(dog_id3, 'roll over')

        sleep(wait)

        assert counters.get_count('roll over') == 3
        assert counters.get_count('fetch ball') == 0
        assert counters.get_count('play dead') == 0

        school.add_trick(dog_id1, 'fetch ball')
        school.add_trick(dog_id2, 'fetch ball')

        sleep(wait)

        assert counters.get_count('roll over') == 3
        assert counters.get_count('fetch ball') == 2
        assert counters.get_count('play dead') == 0

        school.add_trick(dog_id1, 'play dead')

        sleep(wait)

        assert counters.get_count('roll over') == 3
        assert counters.get_count('fetch ball') == 2
        assert counters.get_count('play dead') == 1

        runner.stop()


Single-threaded runner
======================

We can run the system with the :class:`~eventsourcing.system.SingleThreadedRunner`.

.. code-block:: python

    from eventsourcing.system import SingleThreadedRunner

    test(system, SingleThreadedRunner)


The applications will use the default POPO persistence module, because the environment variable
``PERSISTENCE_MODULE`` has not been set.

Multi-threaded runner
=====================

We can also run the system with the :class:`~eventsourcing.system.MultiThreadedRunner`.

.. code-block:: python

    from eventsourcing.system import MultiThreadedRunner

    test(system, MultiThreadedRunner, wait=0.1)


SQLite environment
==================

We can also run the system after configuring the applications to use the library's SQLite persistence module.
In the example below, the applications use an in-memory SQLite database.

.. code-block:: python

    import os


    # Use SQLite for persistence.
    os.environ['PERSISTENCE_MODULE'] = 'eventsourcing.sqlite'

    # Use a separate in-memory database for each application.
    os.environ['SQLITE_DBNAME'] = ':memory:'

    # Run the system tests.
    test(system, SingleThreadedRunner)

When running the system with the multi-threaded runner and SQLite databases, we need to be
careful to use separate databases for each application. We could use a file-based
database, but here we will use in-memory SQLite databases. Because we need SQLite's in-memory
databases to support multi-threading, we need to enable SQLite's shared cache. Because we
need to enable the shared cache, and we need more than one database in the same operating
system process, we also need to use named in-memory databases. In order to distinguish
environment variables for different applications in a system, the environment variable names
can be prefixed with the application name.

.. code-block:: python

    # Use separate named in-memory databases in shared cache.
    os.environ['DOGSCHOOL_SQLITE_DBNAME'] = 'file:dogschool?mode=memory&cache=shared'
    os.environ['COUNTERS_SQLITE_DBNAME'] = 'file:counters?mode=memory&cache=shared'

    # Run the system tests.
    test(system, MultiThreadedRunner, wait=0.2)


PostgreSQL Environment
======================

We can also run the system with the library's PostgreSQL persistence module.

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

We can use the same PostgreSQL database for different applications in a system,
because the PostreSQL persistence module creates different tables for each application.

However, before running the test again with PostgreSQL, we need to reset the trick counts,
because they are being stored in a durable database and so would simply accumulate. We can
do this by deleting the database tables for the system.

.. code-block:: python

    from eventsourcing.postgres import PostgresDatastore
    from eventsourcing.tests.postgres_utils import drop_postgres_table

    db = PostgresDatastore(
        "eventsourcing",
        "127.0.0.1",
        "5432",
        "eventsourcing",
        "eventsourcing",
    )
    drop_postgres_table(db, "dogschool_events")
    drop_postgres_table(db, "counters_events")
    drop_postgres_table(db, "counters_tracking")

After resetting the trick counts, we can run the system again with the multi-threaded runner.

.. code-block:: python

    test(system, MultiThreadedRunner, wait=0.2)

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
