===================================
Tutorial - Part 1 - Getting started
===================================

Part 1 of this :doc:`tutorial </topics/tutorial>` introduces the library's
:class:`~eventsourcing.domain.Aggregate` and :class:`~eventsourcing.application.Application`
classes, showing and explaining how they can be used together to
write an event-sourced application in Python.

Python classes
==============

This tutorial depends on a basic understanding of `Object-Oriented Programming
in Python <https://realpython.com/python3-object-oriented-programming/>`_.

Before we begin, let's review object classes in Python. The example below is taken
from the `Class and Instance Variables <https://docs.python.org/3/tutorial/classes.html#class-and-instance-variables>`_
section of the Python docs.

The example below defines a ``Dog`` class. An instance of the ``Dog`` class can be constructed by calling
the ``Dog`` class with a ``name`` argument. An instance of ``Dog`` will have a ``name`` attribute and a
``tricks`` attribute. The ``name`` attribute will be initialized with the given value of the ``name``
argument. The ``tricks`` attribute will be initialized with an empty list. The ``Dog`` class defines a
method called ``add_trick()``. Calling the ``add_trick()`` method on an instance of ``Dog`` will cause
the given value of the argument ``trick`` to be appended to its ``tricks`` attribute.

.. code-block:: python

    class Dog:
        def __init__(self, name):
            self.name = name
            self.tricks = []

        def add_trick(self, trick):
            self.tricks.append(trick)

Let's construct an instance of the ``Dog`` class, by calling the ``Dog`` class with a ``name`` argument.

.. code-block:: python

    dog = Dog(name='Fido')

    assert isinstance(dog, Dog)

The ``__init__()`` method of the ``Dog`` class initialises the instance's ``name`` attribute with
the given value of the ``name`` argument, and the ``tricks`` attribute to be an empty list.

.. code-block:: python

    assert dog.name == 'Fido'
    assert dog.tricks == []

Let's call the method ``add_trick()``. The given value of the ``trick`` argument will be appended
to the object's ``tricks`` attribute.

.. code-block:: python

    dog.add_trick(trick='roll over')

    assert dog.tricks == ['roll over']

This is a simple example of a Python class. In the next section, we will convert the ``Dog`` class to be an event-sourced aggregate.

Event-sourced aggregates
========================

In *Domain-Driven Design*, aggregates are persistent software objects that may change.
Aggregates are persisted by somehow recording their state in a database. When the state
of an aggregate changes, the recorded state in the database is somehow updated.

A conventional way to persist the state of aggregates in *Domain-Driven Design* is to have
a database table for each type of aggregate in the domain model, with one column for each
attribute, and with one row for each aggregate. When a new aggregate is created, a row is
inserted. When an existing aggregate is changed, its row is updated. This approach is known
as "concrete table inheritance".

Event sourcing take this two steps further. Firstly, whenever an aggregate is created or updated,
a decision is encapsulated by an event object, and that event object is used to mutate an aggregate
object. Secondly, rather than recording only the current state of aggregate objects, instead the
event objects are recorded so that the recorded event objects can be used later to reconstruct
aggregate objects. All events can be recorded in the same table, with one row inserted for each
new event. The event objects do not change, and so the rows are not updated.

The important difference for an event-sourced aggregate is that it will generate a sequence of
event objects, and this sequence of event objects will be used to reconstruct the aggregate object.

The software code that can persist and reconstruct event-sourced aggregates can be used in many
different applications.

We can most concisely define event-sourced aggregates in Python
by using the :class:`~eventsourcing.domain.Aggregate` class and
the :func:`@event<eventsourcing.domain.event>` decorator.

.. code-block:: python

    from eventsourcing.domain import Aggregate, event

For example, we can convert the ``Dog`` class into an event-sourced aggregate, by inheriting
from the library's :class:`~eventsourcing.domain.Aggregate` class, and by decorating "command"
methods (methods that change the state of the aggregate) with the library's
:func:`@event<eventsourcing.domain.event>` decorator.

By decorating command methods in this way, event object classes will be defined
according to the method signatures, new event objects will be constructed whenever
the methods are called, and the method bodies will be executed whenever the event
objects are used to mutate aggregate objects.

The changes are highlighted below.

.. code-block:: python
    :emphasize-lines: 1,2,7

    class Dog(Aggregate):
        @event('Registered')
        def __init__(self, name):
            self.name = name
            self.tricks = []

        @event('TrickAdded')
        def add_trick(self, trick):
            self.tricks.append(trick)

As above in the simple example of a Python class, calling this ``Dog`` class will construct a new
instance. Behind the scenes, a ``Dog.Registered`` event is also constructed, but we will return to this later.

.. code-block:: python

    dog = Dog(name='Fido')

The variable ``dog`` is an instance of ``Dog``.

.. code-block:: python

    assert isinstance(dog, Dog)

The ``dog`` object is also an :class:`~eventsourcing.domain.Aggregate`.

.. code-block:: python

    assert isinstance(dog, Aggregate)

As above, the attributes ``name`` and ``tricks`` have been initialised.

.. code-block:: python

    assert dog.name == 'Fido'
    assert dog.tricks == []

Because ``Dog`` inherits from :class:`~eventsourcing.domain.Aggregate`, the ``dog`` object
also has an ``id`` attribute. It happens to be a version 4 UUID. The aggregate's ``id``
can be used to uniquely identify the aggregate in a domain model.

.. code-block:: python

    from uuid import UUID

    assert isinstance(dog.id, UUID)


When we call the method ``add_trick()``, the given value of the ``trick`` argument
is appended to the ``tricks`` attribute. Behind the scenes a ``Dog.TrickAdded`` event
is also constructed.

.. code-block:: python

    dog.add_trick(trick='roll over')

    assert dog.tricks == ['roll over']


The ``Dog`` class is an event-sourced aggregate. An event object was constructed both when
we called the ``Dog`` class, and when we called the ``add_trick()`` method. These two event
objects can be collected from the aggregate object, and recorded, and used later to reconstruct
the aggregate. We can collect newly constructed event objects from the aggregate object by
calling the :func:`~eventsourcing.domain.Aggregate.collect_events` method, which is defined by
the :class:`~eventsourcing.domain.Aggregate` class.

.. code-block:: python

    events = dog.collect_events()

The variable ``events`` is a list of event objects. The event objects in this list are all instances
of the nested class ``Dog.Event``.

.. code-block:: python

    for e in events:
        assert isinstance(e, Dog.Event)

Two event objects were collected.

.. code-block:: python

    assert len(events) == 2

The first event object is a ``Dog.Registered`` event. It has an attribute ``name``.

.. code-block:: python

    assert isinstance(events[0], Dog.Registered)
    assert events[0].name == 'Fido'

The second event object is a ``Dog.TrickAdded`` event. It has an attribute ``trick``.

.. code-block:: python

    assert isinstance(events[1], Dog.TrickAdded)
    assert events[1].trick == 'roll over'

Each event object has a :func:`~eventsourcing.domain.CanMutateAggregate.mutate` method.
We can reconstruct the aggregate object, by calling the
:func:`~eventsourcing.domain.CanMutateAggregate.mutate` methods, in the following way.

.. code-block:: python

    copy = None
    for e in events:
        copy = e.mutate(copy)

    assert copy == dog

This technique for reconstructing aggregates from events is used by the application
repository in the next section.

Event-sourced aggregates can be developed and tested independently
of each other, and independently of any persistence infrastructure.

If you are feeling playful, type the Python code in this example into a Python
console and see for yourself that it works. Use a debugger to step through the
code. Use a testing framework or module to express this code as a unit test.

Event-sourced aggregates are normally used within an application object,
so that aggregate events can be recorded in a database, and so that
aggregates can be reconstructed from recorded events.


Event-sourced applications
==========================

Event-sourced applications combine event-sourced aggregates
with a persistence mechanism to store and retrieve aggregate events.

Event-sourced applications define "command" methods and "query" methods
that can be used by interfaces to get and update the state of an
application without dealing directly with its aggregates.

We can most easily define event-sourced applications by using the
:class:`~eventsourcing.application.Application` class.

.. code-block:: python

    from eventsourcing.application import Application

Using the :class:`~eventsourcing.application.Application` class, and
the the ``Dog`` class, let's define a ``DogSchool`` application.

.. code-block:: python

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

The command methods ``register_dog()`` and ``add_trick()`` use the application's
:func:`~eventsourcing.application.Application.save` method to collect and store
new event objects.

The command method ``add_trick()`` and the query method ``get_dog()`` reconstruct
aggregates from stored events by using the :func:`~eventsourcing.application.Repository.get`
method of the application's repository object.

We can use the ``DogSchool`` class to construct an application object.

.. code-block:: python

    application = DogSchool()

We can create and update aggregates by calling ``register_dog()`` and ``add_trick()``.

.. code-block:: python

    dog_id = application.register_dog(name='Fido')
    application.add_trick(dog_id, trick='roll over')
    application.add_trick(dog_id, trick='fetch ball')

We can get the state of an aggregate by calling ``get_dog()``.

.. code-block:: python

    dog_details = application.get_dog(dog_id)

    assert dog_details['name'] == 'Fido'
    assert dog_details['tricks'] == ('roll over', 'fetch ball')

We can propagate the state of an application by selecting event notifications from
the application's notification log. The notification log presents the events of all
aggregates in an application as a single sequence of event notifications.

.. code-block:: python

    notifications = application.notification_log.select(start=1, limit=10)

    assert len(notifications) == 3
    assert notifications[0].id == 1
    assert notifications[1].id == 2
    assert notifications[2].id == 3

There will be exactly one event notification for each aggregate event that was stored.
The event notifications will be in the same order as the aggregate events were
stored. The events of all aggregates will appear in the notification log.

Please note, when we interacted with the application methods, we
did not directly interact with the aggregates. The aggregates are
encapsulated by the application.

In this way, event-sourced applications can be developed and tested independently.

The :class:`~eventsourcing.application.Application` class, by default,
uses a persistence module which stores events in memory using "plain
old Python objects". Application objects can be configured with environment
variables to use a durable database.

If you are feeling playful, please type the Python code into a Python console
and see for yourself that it works.


Writing tests
=============

It is generally recommended to follow a test-driven approach to the
development of event-sourced applications. You can get started by first
writing a failing test for your application in a Python module,
for example with the following test in a file ``test_application.py``.

.. code-block:: python

    def test_dog_school():

        # Construct the application.
        app = DogSchool()

        # Register a dog.
        dog_id = app.register_dog(name='Fido')

        # Check the dog has been registered.
        assert app.get_dog(dog_id) == {
            'name': 'Fido',
            'tricks': (),
        }

        # Add tricks.
        app.add_trick(dog_id, trick='roll over')
        app.add_trick(dog_id, trick='fetch ball')

        # Check the tricks have been added.
        assert app.get_dog(dog_id) == {
            'name': 'Fido',
            'tricks': ('roll over', 'fetch ball'),
        }


You can begin to develop your application by defining your application
and aggregate classes in the test module. You can then refactor by moving
your application and aggregate classes to separate modules. For example
your application class could be moved to an ``application.py`` file, and
your aggregate classes could be moved to a ``domainmodel.py`` file. See
the "live coding" video :ref:`Event sourcing in 15 minutes <event-sourcing-in-15-minutes>`
for a demonstration of how this can be done.

Project structure
=================

You are free to structure your project files however you wish. It is
generally recommended to put test code and code-under-test in separate
folders.

::

    your_project/__init__.py
    your_project/application.py
    your_project/domainmodel.py
    tests/__init__.py
    tests/test_application.py

If you will have a larger number of aggregate classes, you may wish to
convert the ``domainmodel.py`` file into a Python package, and have a
separate submodule for each aggregate class. To start a new project
with modern tooling, you can use the `template for Python eventsourcing
projects <https://github.com/pyeventsourcing/cookiecutter-eventsourcing#readme>`_.


Exercise
========

Completing this exercise depends on:

* having a working Python installation,
* :doc:`installing the eventsourcing library </topics/installing>`, and
* knowing how to `write and run tests in Python <https://realpython.com/python-testing>`_.

Copy the ``test_dog_school()`` function (see above) into a Python file, for example
``test_application.py``. Then run the test function and see that it fails. Then add
the ``DogSchool`` application and the ``Dog`` aggregate code. Then run the test function
again and see that it passes.

.. code-block:: python

    test_dog_school()

When your code is working, refactor by moving the application and
aggregate classes to separate Python files, for example ``application.py``
and ``domainmodel.py``. After completing your refactorings, run the test
again to make sure your code still works.

If you are feeling playful, you can use a debugger or add some print
statements to step through what happens in the aggregate and application
classes.


Next steps
==========

* For more information about event-sourced aggregates, please
  read :doc:`Part 2 </topics/tutorial/part2>` of this tutorial.
* For more information about event-sourced applications, please
  read :doc:`Part 3 </topics/tutorial/part3>` of this tutorial.
