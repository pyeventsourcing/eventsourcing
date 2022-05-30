===================================
Tutorial - Part 1 - Getting started
===================================

Part 1 of the tutorial introduces event-sourced aggregates and event-sourced applications.

We will discuss how event-sourced aggregates and event-sourced applications
can work in Python.

By the end of this section, you will have an understanding of how to write
event-sourced aggregates and event-sourced application in Python.

This tutorial depends on a `basic understanding of the Python programming language
<https://realpython.com/python-basics/>`_, and `Object-Oriented Programming in Python
<https://realpython.com/python3-object-oriented-programming/>`_.

Python classes
==============

We can define a ``Dog`` class in Python as follows.
This example is taken from the `Class and Instance Variables
<https://docs.python.org/3/tutorial/classes.html#class-and-instance-variables>`_
section of the Python docs.


.. code-block:: python

    class Dog:
        def __init__(self, name):
            self.name = name
            self.tricks = []

        def add_trick(self, trick):
            self.tricks.append(trick)

Having defined a Python class, we can use it to create an instance.

.. code-block:: python

    dog = Dog('Fido')

The ``dog`` object is an instance of the ``Dog`` class.

.. code-block:: python

    assert isinstance(dog, Dog)

The ``__init__()`` method initialises the attributes ``name`` and ``tricks``.

.. code-block:: python

    assert dog.name == 'Fido'
    assert dog.tricks == []

The method ``add_trick()`` appends the argument ``trick`` to the attribute ``tricks``.

.. code-block:: python

    dog.add_trick('roll over')
    assert dog.tricks == ['roll over']

This is a simple example of a Python class.

In the next section, we convert the ``Dog`` class to be an event-sourced aggregate.

Event-sourced aggregate
=======================

A persistent object is an object (such as ``dog`` in the example above) that is
stored in a database. Persistent objects are used in application domain models
to record the state of the application. Persistent objects used for this purpose
are sometimes referred to as 'aggregates'.

The notion of an 'aggregate' was described in the book *Domain-Driven Design*.
Aggregates evolve over time according to a sequence of decisions that they make.
In *Domain-Driven Design*, aggregates are persisted by inserting or updating
database records that represent the current state of the object.

Event sourcing take this a step further, by recording the sequence of decisions
that an aggregate makes as a sequence of event objects, and using the aggregate's
sequence of event objects to reconstruct the current state of the aggregate.

The important difference is that an event-sourced aggregate will generate a
sequence of event objects, and these event objects will be used to evolve the
state of the aggregate object. So let's look at how this can be done.

We can convert the ``Dog`` class into an event-sourced aggregate, by using
the ``Aggregate`` class as its super class, and by using the ``@event``
decorator to decorate methods that change the state of the aggregate. Then,
aggregate event objects will be generated when decorated methods are called,
and the decorated method bodies will used to evolve the state of the aggregate.
The changes are highlighted below.

.. code-block:: python
    :emphasize-lines: 3,4,9

    from eventsourcing.domain import Aggregate, event

    class Dog(Aggregate):
        @event('Registered')
        def __init__(self, name):
            self.name = name
            self.tricks = []

        @event('TrickAdded')
        def add_trick(self, trick):
            self.tricks.append(trick)

As before, we can call the class to create a new instance.

.. code-block:: python

    dog = Dog('Fido')

The object is an instance of ``Dog``. It is also an ``Aggregate``.

.. code-block:: python

    assert isinstance(dog, Dog)
    assert isinstance(dog, Aggregate)

As we might expect, the attributes ``name`` and ``tricks`` have been initialised.

.. code-block:: python

    assert dog.name == 'Fido'
    assert dog.tricks == []

The ``dog`` aggregate also has an ``id`` attribute. The ID is used to uniquely identify
the aggregate within a collection of aggregates. It happens to be a UUID.

.. code-block:: python

    from uuid import UUID

    assert isinstance(dog.id, UUID)

As above, we can call the method ``add_trick()``. The given value is appended to ``tricks``.

.. code-block:: python

    dog.add_trick('roll over')

    assert dog.tricks == ['roll over']

By redefining the ``Dog`` class as an event-sourced aggregate in this way, we can
generate a sequence of event objects that can be recorded and used later to
reconstruct the aggregate.

We can get the events from the aggregate by calling ``collect_events()``.

.. code-block:: python

    events = dog.collect_events()

We can then reconstruct the aggregate by calling ``mutate()`` on the collected event objects.

.. code-block:: python

    copy = None
    for e in events:
        copy = e.mutate(copy)

    assert copy == dog

If you are feeling playful, copy the Python code into a Python console
and see for yourself that it works.

Event-sourced aggregates can be developed and tested independently
of each other, and independently of any persistence infrastructure.

Event-sourced aggregates are normally used within an application object,
so that aggregate events can be recorded in a database, and so that
aggregates can be reconstructed from recorded events.


Event-sourced application
=========================

Event-sourced applications combine event-sourced aggregates
with a persistence mechanism to store and retrieve aggregate events.

Event-sourced applications define "command methods" and "query methods"
that can be used by interfaces to manipulate and access the state of an
application without dealing with it aggregate objects.

We can define event-sourced applications with the ``Application`` class
from the library's :doc:`application module </topics/application>`.

.. code-block:: python

    from eventsourcing.application import Application

Let's define a ``DogSchool`` application that uses the ``Dog`` aggregate class.

We can save aggregates with the application's ``save()`` method, and
we can reconstruct previously saved aggregates with the application
repository's ``get()`` method.

.. code-block:: python

    class DogSchool(Application):
        def register_dog(self, name):
            dog = Dog(name)
            self.save(dog)
            return dog.id

        def add_trick(self, dog_id, trick):
            dog = self.repository.get(dog_id)
            dog.add_trick(trick)
            self.save(dog)

        def get_dog(self, dog_id):
            dog = self.repository.get(dog_id)
            return {'name': dog.name, 'tricks': tuple(dog.tricks)}

The "command" methods ``register_dog()`` and ``add_trick()`` evolve application
state, and the "query" method ``get_dog()`` presents current state.

We can construct an instance of the application by calling the application class.

.. code-block:: python

    application = DogSchool()

We can then create and update aggregates by calling the command methods of the application.

.. code-block:: python

    dog_id = application.register_dog('Fido')
    application.add_trick(dog_id, 'roll over')
    application.add_trick(dog_id, 'fetch ball')

We can view the state of the aggregates by calling application query methods.

.. code-block:: python

    dog_details = application.get_dog(dog_id)

    assert dog_details['name'] == 'Fido'
    assert dog_details['tricks'] == ('roll over', 'fetch ball')

And we can propagate the state of the application as a whole by selecting
event notifications from the application's notification log.

.. code-block:: python

    notifications = application.notification_log.select(start=1, limit=10)

    assert len(notifications) == 3
    assert notifications[0].id == 1
    assert notifications[1].id == 2
    assert notifications[2].id == 3

If you are feeling playful, copy the Python code into a Python console
and see for yourself that it works.

Event-sourced applications can be developed and tested independently
using the library's default persistence infrastructure, which records
stored events in memory using "plain old Python objects".


Writing tests
=============

It is generally recommended to follow a test-driven approach to the
development of event-sourced applications. You can get started by first
writing a failing test for your application in in a Python module,
for example a file ``test_application.py`` with the following test.

.. code-block:: python

    def test_dog_school():

        # Construct the application.
        app = DogSchool()

        # Register a dog.
        dog_id = app.register_dog('Fido')

        # Check the dog has been registered.
        assert app.get_dog(dog_id) == {
            'name': 'Fido',
            'tricks': (),
        }

        # Add tricks.
        app.add_trick(dog_id, 'roll over')
        app.add_trick(dog_id, 'fetch ball')

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
separate submodule for each aggregate class.


Exercise
========

Completing this exercise depends on having a working Python installation,
:doc:`installing the eventsourcing library </topics/installing>`,
and knowing how to `write and run tests in Python <https://realpython.com/python-testing>`_.

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

If you are feeling playful, you can add some more print statements
that show what happens in the aggregate and application classes.


Next steps
==========

* For more information about event-sourced aggregates, please
  read :doc:`Part 2 </topics/tutorial/part2>` of this tutorial.
* For more information about event-sourced applications, please
  read :doc:`Part 3 </topics/tutorial/part3>` of this tutorial.
