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

Having defined a Python class, we can use it to create an instance.

.. code-block:: python

    world = World('Earth')


As we might expect, the `world` object is an instance of the ``World`` class.

.. code-block:: python

    assert isinstance(world, World)


We can see from the the ``__init__()`` method
that attributes ``name`` and ``history`` will be initialised.

.. code-block:: python

    assert world.name == 'Earth'
    assert world.history == []

A ``World`` instance has a method ``make_it_so()`` which
appends the value of ``what`` to ``history``.

.. code-block:: python

    world.make_it_so('Python')
    assert world.history == ['Python']

This is a basic example of how Python classes work.
However, if we want to use this object in future, we will want
to save and reconstruct it. We will want it to be 'persistent'.

Event-sourced aggregate
=======================

A persistent object that changes through a sequence of decisions
corresponds to the notion of an 'aggregate' in Domain-Driven Design.
An 'event-sourced' aggregate is persisted by persisting the decisions
as a sequence of 'events'.
We can use the aggregate base class ``Aggregate`` and the ``@event``
decorator from the :doc:`domain module </topics/domain>` to define
event-sourced aggregates.

.. code-block:: python

    from eventsourcing.domain import Aggregate, event


Let's convert ``World`` into an event-sourced aggregate. The changes are highlighted below.

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


As before, we can call the class to create a new instance.

.. code-block:: python

    world = World('Earth')

The object is an instance of ``World``. It is also an ``Aggregate``.

.. code-block:: python

    assert isinstance(world, World)
    assert isinstance(world, Aggregate)

As we might expect, the attributes ``name`` and ``history`` have been initialised.

.. code-block:: python

    assert world.name == 'Earth'
    assert world.history == []


The aggregate also has an ``id`` attribute. The ID is used to uniquely identify the
aggregate within a collection of aggregates. It happens to be a UUID.

.. code-block:: python

    from uuid import UUID

    assert isinstance(world.id, UUID)


We can call the aggregate method ``make_it_so()``. The given value is appended to ``history``.

.. code-block:: python

    world.make_it_so('Python')

    assert world.history == ['Python']

By redefining the ``World`` class as an event-sourced aggregate in this way,
when we call the class object and the decorated methods, we construct a sequence
of event objects that can be used to reconstruct the aggregate. We can get
the events from the aggregate by calling ``collect_events()``.

.. code-block:: python

    events = world.collect_events()


We can also reconstruct the aggregate by calling ``mutate()`` on the collected event objects.

.. code-block:: python

    copy = None
    for e in events:
        copy = e.mutate(copy)

    assert copy == world


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


Let's define a ``Universe`` application that interacts with ``World`` aggregates.
We can add command methods to create and change aggregates,
and query methods to view current state.
We can save aggregates with the application ``save()`` method, and
get previously saved aggregates with the repository ``get()`` method.


.. code-block:: python

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


We can construct an instance of the application by calling the application class.

.. code-block:: python

    application = Universe()


We can then create and update aggregates by calling methods of the application.

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
