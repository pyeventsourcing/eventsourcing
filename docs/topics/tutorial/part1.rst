===================================
Tutorial - Part 1 - Getting started
===================================

In Part 1 of this tutorial, we will discuss how event-sourced aggregates
and event-sourced applications can work in Python.

By the end of this section, you will have an understanding of how to write
event-sourced aggregates and event-sourced applications in Python.

This tutorial depends on a basic understanding of `Object-Oriented Programming
in Python <https://realpython.com/python3-object-oriented-programming/>`_.

Python classes
==============

Let's briefly review how to write and use object classes in Python.

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

Having defined a Python class, we can use it to create an instance of the class.

.. code-block:: python

    dog = Dog(name='Fido')

The ``dog`` object is an instance of the ``Dog`` class.

.. code-block:: python

    assert isinstance(dog, Dog)

The ``__init__()`` method initialises the attributes ``name`` and ``tricks``.

.. code-block:: python

    assert dog.name == 'Fido'
    assert dog.tricks == []

The method ``add_trick()`` appends the argument ``trick`` to the attribute ``tricks``.

.. code-block:: python

    dog.add_trick(trick='roll over')
    assert dog.tricks == ['roll over']

This is a simple example of a Python class.

In the next section, we convert the ``Dog`` class to be an event-sourced aggregate.

Event-sourced aggregate
=======================

We can define event-sourced aggregates with the library's ``Aggregate`` class
and ``@event`` decorator.

.. code-block:: python

    from eventsourcing.domain import Aggregate, event

Aggregates are persistent software objects that evolve over time. In the
book *Domain-Driven Design*, aggregates are persisted by recording its
current state of the aggregate in a database. When the state of the
aggregate changes, the recorded state in the database is updated.

Event sourcing take this two steps further. Firstly, each change that an
aggregate can experience is split into two stages: a decision that is
encapsulated by an event object, and the mutation of the aggregate state
according to that event object. And secondly, rather than recording the
current state after the aggregate has changed, the event objects are recorded.
The recorded sequence of event objects can then be used to reconstruct the
current state of the aggregate.

The important difference for the aggregate is that when it is event-sourced,
it will generate a sequence of event objects, one for each decision, and these
event objects will be used to evolve the state of the aggregate object. Let's
look at how this can be done.

Let's convert the ``Dog`` class into an event-sourced aggregate, by inheriting
from the library's ``Aggregate`` class, and by decorating methods that change
the state of the aggregate with the library's ``@event`` decorator.
Aggregate event objects will then be generated when decorated methods are called, and
the decorated method bodies will be used to evolve the state of the aggregate.
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

We can call the ``Dog`` class to create a new instance.

.. code-block:: python

    dog = Dog(name='Fido')

The object is an instance of ``Dog``. It is also an ``Aggregate``.

.. code-block:: python

    assert isinstance(dog, Dog)
    assert isinstance(dog, Aggregate)

The attributes ``name`` and ``tricks`` have been initialised.

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

    dog.add_trick(trick='roll over')

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

We can define event-sourced applications with the library's ``Application`` class.

.. code-block:: python

    from eventsourcing.application import Application

Event-sourced applications combine event-sourced aggregates
with a persistence mechanism to store and retrieve aggregate events.

Event-sourced applications define "command methods" and "query methods"
that can be used by interfaces to manipulate and access the state of an
application, without dealing directly with its aggregates.

Let's define a ``DogSchool`` application that uses the ``Dog`` aggregate class.
The command methods ``register_dog()`` and ``add_trick()`` evolve application
state. The query method ``get_dog()`` presents current state.

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

The application's ``save()`` method collects and stores aggregate event objects.
The application repository's ``get()`` method retrieves an aggregate's stored
events, and reconstructs the aggregate instance from these event objects.

We can construct an instance of the application by calling the application class.

.. code-block:: python

    application = DogSchool()

We can then create and update aggregates by calling the application's command methods.

.. code-block:: python

    dog_id = application.register_dog(name='Fido')
    application.add_trick(dog_id, trick='roll over')
    application.add_trick(dog_id, trick='fetch ball')

We can view the state of the aggregates by calling application's query methods.

.. code-block:: python

    dog_details = application.get_dog(dog_id)

    assert dog_details['name'] == 'Fido'
    assert dog_details['tricks'] == ('roll over', 'fetch ball')

And we can propagate the state of the application by selecting
event notifications from the application's notification log.

.. code-block:: python

    notifications = application.notification_log.select(start=1, limit=10)

    assert len(notifications) == 3
    assert notifications[0].id == 1
    assert notifications[1].id == 2
    assert notifications[2].id == 3

There will be one event notification for each aggregate event that was stored.
The event notifications will be in the same order as the aggregate events were
stored. The events of all aggregates will appear in the notification log.

If you are feeling playful, copy the Python code into a Python console
and see for yourself that it works.

Event-sourced applications can be developed and tested independently
using the library's default persistence infrastructure, which records
stored events in memory using "plain old Python objects".


Writing tests
=============

It is generally recommended to follow a test-driven approach to the
development of event-sourced applications. You can get started by first
writing a failing test for your application in a Python module,
for example a file ``test_application.py`` with the following test.

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

If you are feeling playful, you can use a debugger or add some print
statements to step through what happens in the aggregate and application
classes.


Next steps
==========

* For more information about event-sourced aggregates, please
  read :doc:`Part 2 </topics/tutorial/part2>` of this tutorial.
* For more information about event-sourced applications, please
  read :doc:`Part 3 </topics/tutorial/part3>` of this tutorial.
