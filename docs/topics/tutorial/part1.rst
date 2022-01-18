===================================
Tutorial - Part 1 - Getting Started
===================================

Python classes
==============

This tutorial depends on a basic understanding of
`Python classes <https://docs.python.org/3/tutorial/classes.html>`__.

For example, using Python we can define a ``Dog`` class as follows.

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


As we might expect, the ``dog`` object is an instance of the ``Dog`` class.

.. code-block:: python

    assert isinstance(dog, Dog)


We can see from the the ``__init__()`` method
that attributes ``name`` and ``tricks`` will be initialised.

.. code-block:: python

    assert dog.name == 'Fido'
    assert dog.tricks == []

A ``Dog`` instance has a method ``add_trick()`` which
appends the value of ``trick`` to ``tricks``.

.. code-block:: python

    dog.add_trick('roll over')
    assert dog.tricks == ['roll over']

This is a basic example of how Python classes work.
However, if we want to use this object in future, we will want
to save and reconstruct it. We will want it to be 'persistent'.

Event-sourced aggregate
=======================

A persistent object that changes through a sequence of decisions
corresponds to the notion of an 'aggregate' in the book Domain-Driven Design.
An 'event-sourced' aggregate is persisted by persisting the decisions
as a sequence of 'events'.
We can use the aggregate base class ``Aggregate`` and the ``@event``
decorator from the :doc:`domain module </topics/domain>` to define an
event-sourced aggregate.

.. code-block:: python

    from eventsourcing.domain import Aggregate, event


Let's convert ``Dog`` into an event-sourced aggregate. The changes are highlighted below.

.. code-block:: python
    :emphasize-lines: 1,2,7

    class Dog(Aggregate):
        @event('Created')
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


The aggregate also has an ``id`` attribute. The ID is used to uniquely identify the
aggregate within a collection of aggregates. It happens to be a UUID.

.. code-block:: python

    from uuid import UUID

    assert isinstance(dog.id, UUID)


We can call the aggregate method ``add_trick()``. The given value is appended to ``tricks``.

.. code-block:: python

    dog.add_trick('roll over')

    assert dog.tricks == ['roll over']

By redefining the ``Dog`` class as an event-sourced aggregate in this way,
when we call the class object and the decorated methods, we construct a sequence
of event objects that can be used to reconstruct the aggregate. We can get
the events from the aggregate by calling ``collect_events()``.

.. code-block:: python

    events = dog.collect_events()


We can also reconstruct the aggregate by calling ``mutate()`` on the collected event objects.

.. code-block:: python

    copy = None
    for e in events:
        copy = e.mutate(copy)

    assert copy == dog


Interactions with aggregates usually occur in an application, where collected
events can be persisted and used to reconstruct aggregates.


Event-sourced application
=========================

An event-sourced application comprises many event-sourced aggregates,
and a persistence mechanism to store and retrieve aggregate events.
We can use the library's ``Application`` base class to define
event-sourced applications.

.. code-block:: python

    from eventsourcing.application import Application


Let's define a ``Universe`` application that interacts with ``Dog`` aggregates.
We can add command methods to create and change aggregates,
and query methods to view current state.
We can save aggregates with the application ``save()`` method, and
get previously saved aggregates with the repository ``get()`` method.


.. code-block:: python

    class Universe(Application):
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


We can construct an instance of the application by calling the application class.

.. code-block:: python

    application = Universe()


We can then create and update aggregates by calling the command methods of the application.

.. code-block:: python

    dog_id = application.register_dog('Fido')
    application.add_trick(dog_id, 'roll over')
    application.add_trick(dog_id, 'fetch ball')
    application.add_trick(dog_id, 'play dead')


We can view the state of the aggregates by calling application query methods.

.. code-block:: python

    dog_details = application.get_dog(dog_id)

    assert dog_details['name'] == 'Fido'
    assert dog_details['tricks'] == ('roll over', 'fetch ball', 'play dead')

And we can propagate the state of the application as a whole by selecting
event notifications from the application's notification log.

.. code-block:: python

    notifications = application.notification_log.select(start=1, limit=10)

    assert len(notifications)
    assert notifications[0].id == 1
    assert notifications[1].id == 2
    assert notifications[2].id == 3

Any number of different kinds of event-sourced applications can
be defined in this way.


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


Writing tests
=============

You can get started with your event sourcing project by first writing a failing test
in ``tests.py``, then define your application and aggregate classes in the test module.
You can then refactor by moving aggregate and application classes to separate Python modules.
You can also convert these modules to packages if you want to break things up into smaller
modules.

.. code-block:: python

    def test():

        # Construct application object.
        app = Universe()

        # Call application command methods.
        dog_id = app.register_dog('Fido')
        app.add_trick(dog_id, 'roll over')
        app.add_trick(dog_id, 'fetch ball')

        # Call application query method.
        assert app.get_dog(dog_id) == {
            'name': 'Fido',
            'tricks': (
                'roll over',
                'fetch ball'
            )
        }

Exercise
========

Try it for yourself by copying the code snippets above and running the test.


.. code-block:: python

    test()


Next steps
==========

For more information about event-sourced aggregates, please read through
:doc:`Part 2 </topics/tutorial/part2>` of this tutorial.
