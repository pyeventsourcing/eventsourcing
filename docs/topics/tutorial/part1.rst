===================================
Tutorial - Part 1 - Getting started
===================================

Part 1 of the tutorial introduces event-sourced aggregates and event-sourced applications.

We will discuss how event-sourced aggregates and event-sourced applications
can work in Python.

By the end of this section, you will have an understanding of how to write
event-sourced aggregates and event-sourced application in Python.

Completing the exercise at the end of this section depends on having a working
Python installation, and having :doc:`installed the eventsourcing library </topics/installing>`.

Python classes
==============

This tutorial depends on a basic understanding of
`Python classes <https://docs.python.org/3/tutorial/classes.html>`_.
This example is taken from the `Class and Instance Variables
<https://docs.python.org/3/tutorial/classes.html#class-and-instance-variables>`_
section of the Python docs.

We can define a ``Dog`` class in Python as follows.

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

A persistent object that changes through a sequence of decisions
corresponds to the notion of an 'aggregate' in the book *Domain-Driven Design*.
In the book, aggregates are persisted by inserting or updating
database records that represent the current state of the object.

Event-sourced aggregates take this a step further, by recording the sequence
of decisions that it makes as a sequence of event objects, and using the aggregate's
sequence of event objects to reconstruct the current state of the aggregate.

The important difference is that an event-sourced aggregate will generate a
sequence of event objects, and these event objects will be used to evolve the
state of the aggregate object.

We can convert the ``Dog`` class into an event-sourced aggregate using
the ``Aggregate`` class and ``@event`` decorator from the library's
:doc:`domain module </topics/domain>`. Aggregate event objects will be
generated when decorated methods are called. The decorated method bodies
will used to evolve the state of the aggregate. The changes are highlighted
below.

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


Event-sourced aggregates can be developed and tested independently.

.. code-block:: python

    def test_dog():
        dog = Dog('Fido')
        assert dog.name == 'Fido'
        assert dog.tricks == []

        dog.add_trick('roll over')
        assert dog.tricks == ['roll over']

    # Run the test
    test_dog()


Event-sourced aggregates are normally used within an application object,
so that aggregate events can be recorded in a database, and so that
aggregates can be reconstructed from recorded events.


Event-sourced application
=========================

Event-sourced applications combine event-sourced aggregates
with a persistence mechanism to store and retrieve aggregate events.

Event-source applications define command and query methods
that can be used by interfaces to manipulate and access
the state of an application without dealing with it aggregate
objects.

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

Many different kinds of event-sourced applications can be defined in this way.


Project structure
=================

You are free to structure your project files however you wish. You
may wish to put your application class in a file named ``application.py``,
and your aggregate classes in a file named ``domainmodel.py``.

::

    your_project/__init__.py
    your_project/application.py
    your_project/domainmodel.py
    tests/__init__.py
    tests/test_application.py

It is generally recommended to put test code and code-under-test in separate
folders.

Writing tests
=============

It is generally recommended to follow a test-driven approach to the development of
event-sourced applications. You can get started with your event sourcing project by
first writing a failing test in a Python file, for example a file ``test_application.py``.
You can begin by defining your application and aggregate classes in this file. You
can then refactor by moving aggregate and application classes to separate Python
modules. You can convert these modules to packages if you want to split things up
into smaller modules.

.. code-block:: python

    def test_dog_school():

        # Construct application object.
        app = DogSchool()

        # Call application command methods.
        dog_id = app.register_dog('Fido')
        app.add_trick(dog_id, 'roll over')
        app.add_trick(dog_id, 'fetch ball')

        # Call application query method.
        assert app.get_dog(dog_id) == {
            'name': 'Fido',
            'tricks': ('roll over', 'fetch ball'),
        }

        print("test_dog_school: PASSED")

Exercise
========

Try it for yourself by typing the code snippets into a Python file
and calling the test function.

.. code-block:: python

    test_dog_school()

If everything goes well, you should be able to run the Python file without error. The
following message should be printed.

.. code-block:: text

    test_dog_school: PASSED


If you are feeling playful, you can add some more print statements
that show what happens in the aggregate and application classes.

When your code is working, refactor by moving the aggregate and application classes to
separate Python modules. Run the test again to make sure your code still works.

Next steps
==========

* For more information about event-sourced aggregates, please
  read :doc:`Part 2 </topics/tutorial/part2>` of this tutorial.
* For more information about event-sourced applications, please
  read :doc:`Part 3 </topics/tutorial/part3>` of this tutorial.
