=================
Tutorial - Part 2
=================

As we saw in :doc:`Part 1 </topics/tutorial/part1>`, we can
use the aggregate base class ``Aggregate`` and the ``@event``
decorator to define event-sourced aggregates in Python.

.. code-block:: python

    from eventsourcing.domain import Aggregate, event

We have seen what we can do with event-sourced aggregates and
applications. Let's look at how event-sourced aggregates work
in more detail.

Aggregates in more detail
=========================

Let's define the simplest possible event-sourced aggregate, by
simply subclassing ``Aggregate``.

.. code-block:: python

    class World(Aggregate):
        pass


In the usual way with Python classes, we can create a new class instance by
calling the class object.

.. code-block:: python

    world = World()

    assert isinstance(world, World)


Normally when a class instance is constructed by calling the class object, Python directly
instantiates and initialises the class instance. However, when a subclass of ``Aggregate``
is called, the class instance is constructed in a slightly indirect way.

Firstly, an event object is constructed. This event object represents the fact the aggregate
was "created". Then, this event object is used to construct and initialise the aggregate
object. The point being, that same event object can be used again to reconstruct the aggregate
object in future.

To reconstruct the aggregate object from the event object, we firstly need to get hold
of the new event object. Fortunately, the new event object is not lost. It is held by
the aggregate in an internal list. We can collect the event object from our aggregate by
calling the aggregate's ``collect_events()`` method. This method is kindly provided by the
aggregate base class.

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

Next, let's talk about aggregate events in more detail.

Events in more detail
=====================

When the aggregate class code was interpreted by Python, a "created" event
class was automatically defined on the aggregate class object. The name of the
"created" event class was given the default name "Created".

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
        def __init__(self, name):
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

    assert len(events) == 1
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
        def __init__(self, name):
            self.name = name
            self.history = []

        @event('SomethingHappened')
        def make_it_so(self, what):
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
these two events by calling ``collect_events()``.

.. code-block:: python

    events = world.collect_events()

    assert len(events) == 2

Just like the "started" event has a ``name`` attribute, so the
"something happened" event has a ``what`` attribute.

.. code-block:: python

    assert isinstance(events[0], World.Started)
    assert events[0].name == 'Earth'

    assert isinstance(events[1], World.SomethingHappened)
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
    for e in events:
        copy = e.mutate(copy)

    assert copy == world

Calling the aggregate's ``collect_events()`` method is what happens when
an application's ``save()`` method is called. Calling the ``mutate()``
methods of saved events' is how an application repository reconstructs
aggregates from saved events when its ``get()`` is called.


You can try all of this for yourself by copying the code snippets above.

Exercise
========

Define a ``Dog`` aggregate, that has a given ``name`` and a list of ``tricks``.
Define a method ``add_trick()`` that adds new tricks. Copy the test below and make it pass.

..
    #include-when-testing
..
    class Dog(Aggregate):
        @event('Named')
        def __init__(self, name):
            self.name = name
            self.tricks = []

        @event('TrickAdded')
        def add_trick(self, trick):
            self.tricks.append(trick)


.. code-block:: python

    def test():

        # Give a dog a name, and some tricks.
        fido = Dog(name='Fido')
        fido.add_trick('fetch ball')
        fido.add_trick('roll over')
        fido.add_trick('play dead')

        # Check the state of the aggregate.
        assert fido.name == 'Fido'
        assert fido.tricks == [
            'fetch ball',
            'roll over',
            'play dead',
        ]

        # Check the aggregate events.
        events = fido.collect_events()
        assert len(events) == 4
        assert isinstance(events[0], Dog.Named)
        assert events[0].name == 'Fido'
        assert isinstance(events[1], Dog.TrickAdded)
        assert events[1].trick == 'fetch ball'
        assert isinstance(events[2], Dog.TrickAdded)
        assert events[2].trick == 'roll over'
        assert isinstance(events[3], Dog.TrickAdded)
        assert events[3].trick == 'play dead'

        # Reconstruct aggregate from events.
        copy = None
        for e in events:
            copy = e.mutate(copy)
        assert copy == fido

        # Create and test another aggregate.
        buddy = Dog(name='Buddy')
        assert fido != buddy
        events = buddy.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], Dog.Named)
        assert events[0].name == 'Buddy'
        assert events[0].mutate(None) == buddy


..
    #include-when-testing
..
    test()
