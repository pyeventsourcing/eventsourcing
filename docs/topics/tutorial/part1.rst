===================================
Tutorial - Part 1 - Getting Started
===================================

Python classes
==============

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
will want it to be 'persistent'.

Event-sourced aggregate
=======================

A persistent object that changes through a sequence of individual
decisions corresponds to the notion of an 'aggregate' in Domain-Driven
Design.

An 'event-sourced' aggregate is persisted by persisting the individual
decisions that make the aggregate what it is. The sequence of decisions
is recorded as a sequence of immutable 'event' objects. The event objects
do not change.

In the simple example above, the sequence was: a "world was created"
and then "Python happened". We can easily convert the example Python class
above into a fully-functioning event-sourced aggregate by using this library's
``Aggregate`` class and its ``@event`` `function decorator <https://docs.python.org/3/glossary.html#term-decorator>`__.

We can use the aggregate base class ``Aggregate`` and the decorator
``@event`` from the :doc:`domain module </topics/domain>` to define
event-sourced aggregates in Python.


.. code-block:: python

    from eventsourcing.domain import Aggregate, event


An event-sourced aggregate constructs, and its state is determined by, a sequence of events.

Let's convert the ``World`` class above into an event-sourced aggregate.
We can define an event-sourced ``World`` class by inheriting from ``Aggregate``.
We can use the ``@event`` decorator on command methods to define aggregate events.
The changes are highlighted below.

.. code-block:: python
    :emphasize-lines: 1,2,7

    class World(Aggregate):
        @event('Created')
        def __init__(self, name):
            self.name = name
            self.history = []

        @event('SomethingHappened')
        def make_it_so(self, what):
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
=========================

An event-sourced application comprises many event-sourced aggregates,
and a persistence mechanism to store and retrieve aggregate events.

We can use the application base class ``Application`` from the
:doc:`application module </topics/application>` to define event-sourced applications
in Python.

.. code-block:: python

    from eventsourcing.application import Application


Let's define a ``Universe`` application that interacts with ``World`` aggregates.
We can define an event-sourced application with this library's ``Application``
base class. We can add command methods (to create and update aggregates)
and query methods (to view current state).

.. code-block:: python

    class Universe(Application):
        def create_world(self, name):
            world = World(name)
            self.save(world)
            return world.id

        def make_it_so(self, world_id, what):
            world = self._get_world(world_id)
            world.make_it_so(what)
            self.save(world)

        def get_history(self, world_id):
            return self._get_world(world_id).history

        def _get_world(self, world_id):
            return self.repository.get(world_id)

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
        world_id = app.create_world('Earth')
        app.make_it_so(world_id, 'dinosaurs')
        app.make_it_so(world_id, 'trucks')

        # Call application query method.
        assert app.get_history(world_id) == [
            'dinosaurs',
            'trucks'
        ]

Exercise
========

Try it for yourself by copying the code snippets above and running the test.


.. code-block:: python

    test()


Next steps
==========

For more information about event-sourced aggregates, please read through
:doc:`Part 2 </topics/tutorial/part2>` of this tutorial.
