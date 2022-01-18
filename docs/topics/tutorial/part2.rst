==============================
Tutorial - Part 2 - Aggregates
==============================

As we saw in :doc:`Part 1 </topics/tutorial/part1>`, we can
use the aggregate base class ``Aggregate``, combined with the
``@event`` decorator, to define event-sourced aggregates in Python.

.. code-block:: python

    from eventsourcing.domain import Aggregate, event

Let's look at how event-sourced aggregates work in more detail.

Aggregates in more detail
=========================

Let's define the simplest possible event-sourced aggregate, by
simply subclassing ``Aggregate``.

.. code-block:: python

    class Dog(Aggregate):
        pass


In the usual way with Python classes, we can create a new class instance by
calling the class object.

.. code-block:: python

    dog = Dog()

    assert isinstance(dog, Dog)


Normally when a class instance is constructed by calling the class object, Python directly
instantiates and initialises the class instance. However, when a subclass of ``Aggregate``
is called, firstly an event object is constructed. This event object represents the fact that
the aggregate was "created". Then, this event object is used to construct and initialise
the aggregate object. The aggregate object is returned to the caller of the class.

The new event object is held by the aggregate in an internal list of "pending events". We can
collect pending events from aggregates by calling the aggregate's ``collect_events()`` method,
which is defined on the ``Aggregate`` base class.

.. code-block:: python

    events = dog.collect_events()

    assert len(events) == 1

The event object can be recorded and used to reconstruct the aggregate
object. To reconstruct the aggregate object, we can simply call the
event object's ``mutate()`` method.

.. code-block:: python

    copy = events[0].mutate(None)

    assert copy == dog

Using events to determine the state of an aggregate is the essence of
event sourcing. Calling the event's ``mutate()`` method is exactly how
the aggregate object was constructed when the aggregate class was called.

Next, let's talk about aggregate events in more detail.

"Created" events
================

When the aggregate class code was interpreted by Python, a "created" event
class was automatically defined on the aggregate class object. The name of the
"created" event class was given the default name "Created".

The general occurrence of creating aggregate objects requires a general
name. The term "created" is used here for this purpose. Naturally, we will
need to think of suitable names for the particular aggregate events we will
define in our domain models, but sadly the library can't us help with
that.

.. code-block:: python

    assert isinstance(Dog.Created, type)


The event we collected from the aggregate is an instance of ``Dog.Created``.

.. code-block:: python

    assert isinstance(events[0], Dog.Created)


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

    class Dog(Aggregate):
        @event('Registered')
        def __init__(self, name):
            self.name = name


By specifying the name of the "created" event to be ``'Registered'``, an event
class with this name is defined on the aggregate class.

.. code-block:: python

    assert isinstance(Dog.Registered, type)


We can call such events "created" events. They are the initial event in the
aggregate's sequence of aggregate events. They inherit from the base class
"created" event, which has a method ``mutate()`` that knows how to construct
and initialise aggregate objects.

.. code-block:: python

    assert issubclass(Dog.Registered, Aggregate.Created)


Again, as above, we can create a new aggregate instance by calling
the aggregate class. But this time, we need to provide a value for
the ``name`` argument.

..
    #include-when-testing
..
    import eventsourcing.utils
    eventsourcing.utils._topic_cache.clear()

.. code-block:: python

    dog = Dog('Fido')


As we might expect, the given ``name`` is used to initialise the ``name``
attribute of the aggregate.

.. code-block:: python

    assert dog.name == 'Fido'


We can call ``collect_events()`` to get the "created" event from
the aggregate object. We can see the event object is an instance of
the class ``Dog.Registered``.

.. code-block:: python

    events = dog.collect_events()

    assert len(events) == 1
    assert isinstance(events[0], Dog.Registered)


The attributes of an event class specified by using the ``@event`` decorator
are derived from the signature of the decorated method. Hence, the event
object has a ``name`` attribute, which follows from the signature of the
aggregate's ``__init__()`` method.

.. code-block:: python

    assert events[0].name == 'Fido'


The "created" event object can be used to construct another object with the
same state as the original aggregate object. That is, it can be used to
reconstruct the initial current state of the aggregate.

.. code-block:: python

    copy = events[0].mutate(None)
    assert copy == dog

Note what's happening there.  We start with nothing - ``None`` - and end up with an instance of ``Dog`` that
has the same state as the original ``dog`` object.  Note also that ``dog`` and ``copy`` are different objects
with the same type and state, not two references to the same Python object.

.. code-block:: python

    assert copy.name == 'Fido'
    assert id(copy) != id(dog)


Subsequent events
=================

We can take this further by defining a second method that will be used
to change the aggregate object after it has been created.

Let's firstly adjust the ``__init__()`` to initialise a ``tricks``
attribute with an empty list. Then let's also define a ``add_trick()``
method that appends to this list, and decorate this method with
the ``@event`` decorator. The changes are highlighted below.

.. code-block:: python
    :emphasize-lines: 8,10-12

    from eventsourcing.domain import Aggregate, event


    class Dog(Aggregate):
        @event('Registered')
        def __init__(self, name):
            self.name = name
            self.tricks = []

        @event('TrickAdded')
        def add_trick(self, trick):
            self.tricks.append(trick)


By decorating the ``add_trick()`` method with the ``@event`` decorator,
an event class ``TrickAdded`` was automatically defined on the
aggregate class.

.. code-block:: python

    assert isinstance(Dog.TrickAdded, type)

The event will be triggered when the method is called. The
body of the method will be used by the event to mutate the
state of the aggregate object.

Let's create an aggregate instance.

..
    #include-when-testing
..
    import eventsourcing.utils
    eventsourcing.utils._topic_cache.clear()

.. code-block:: python

    dog = Dog('Fido')

As we might expect, the ``name`` of the aggregate object is ``'Earth``,
and the ``tricks`` attribute is an empty list.

.. code-block:: python

    assert dog.name == 'Fido'
    assert dog.tricks == []

Now let's call ``add_trick()`` with the value ``'roll over'`` as the argument.

.. code-block:: python

    dog.add_trick('roll over')


The ``tricks`` list now has one item, ``'roll over'``,
the value we passed when calling ``add_trick()``.

.. code-block:: python

    assert dog.tricks == ['roll over']

Creating and updating the aggregate caused two events to occur,
a "registered" event and a "trick added" event. We can collect
these two events by calling ``collect_events()``.

.. code-block:: python

    events = dog.collect_events()

    assert len(events) == 2

Just like the "registered" event has a ``name`` attribute, so the
"trick added" event has a ``trick`` attribute.

.. code-block:: python

    assert isinstance(events[0], Dog.Registered)
    assert events[0].name == 'Fido'

    assert isinstance(events[1], Dog.TrickAdded)
    assert events[1].trick == 'roll over'

The attributes of the event objects follow from the signatures of the
decorated methods. The ``__init__()`` method has a ``name`` argument
and so the "registered" event has a ``name`` attribute. The ``add_trick()``
method has a ``trick`` argument, and so the "trick added" event
has a ``trick`` attribute. The arguments of a method decorated with ``@event``
are used to define the attributes of an event class.

Just like when the ``Dog`` class is called the constructor arguments are used to
create a ``Dog.Registered`` event object, similarly when the ``add_trick()`` method
is called, the values of the method arguments are used to construct a
``Dog.TrickAdded`` event object. The method body is then executed with the
attributes of the event. The resulting state of the aggregate is the same as if the
method were not decorated. The important difference is that a sequence of events is
generated.

This sequence of events can be used in future to reconstruct the current state
of the aggregate, as shown below.

.. code-block:: python

    copy = None
    for e in events:
        copy = e.mutate(copy)

    assert copy == dog

To put this in the context of aggregates being used within an application:
calling the aggregate's ``collect_events()`` method is what happens when
an application's ``save()`` method is called, and calling the ``mutate()``
methods of saved events' is how an application repository reconstructs
aggregates from saved events when its ``get()`` is called.

You can try all of this for yourself by copying the code snippets above.


Exercise
========

Define a ``Dog`` aggregate, that has a given ``name`` and a list of ``tricks``.
Define a method ``add_trick()`` that adds a new trick. Specify the name of
the "created" event to be ``'Named'`` and the name of the subsequent event
to be ``'TrickAdded'``. Copy the test below and make it pass.

..
    #include-when-testing
..
    class Todos(Aggregate):
        @event('Started')
        def __init__(self, name):
            self.name = name
            self.items = []

        @event('ItemAdded')
        def add_item(self, item):
            self.items.append(item)


.. code-block:: python

    def test():

        # Start a list of todos, and add some items.
        todos1 = Todos(name='Shopping list')
        todos1.add_item('bread')
        todos1.add_item('milk')
        todos1.add_item('eggs')

        # Check the state of the aggregate.
        assert todos1.name == 'Shopping list'
        assert todos1.items == [
            'bread',
            'milk',
            'eggs',
        ]

        # Check the aggregate events.
        events = todos1.collect_events()
        assert len(events) == 4
        assert isinstance(events[0], Todos.Started)
        assert events[0].name == 'Shopping list'
        assert isinstance(events[1], Todos.ItemAdded)
        assert events[1].item == 'bread'
        assert isinstance(events[2], Todos.ItemAdded)
        assert events[2].item == 'milk'
        assert isinstance(events[3], Todos.ItemAdded)
        assert events[3].item == 'eggs'

        # Reconstruct aggregate from events.
        copy = None
        for e in events:
            copy = e.mutate(copy)
        assert copy == todos1

        # Create and test another aggregate.
        todos2 = Todos(name='Household repairs')
        assert todos1 != todos2
        events = todos2.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], Todos.Started)
        assert events[0].name == 'Household repairs'
        assert events[0].mutate(None) == todos2

..
    #include-when-testing
..
    test()


Next steps
==========

For more information about event-sourced applications, please read through
:doc:`Part 3 </topics/tutorial/part3>` of this tutorial.
