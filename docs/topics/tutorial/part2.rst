==============================
Tutorial - Part 2 - Aggregates
==============================

In :doc:`Part 1 </topics/tutorial/part1>` we learned
how to use the ``Aggregate`` class and the ``@event``
decorator to define an event-sourced aggregate in Python,
and how to use the ``Application`` class to define an
event-sourced application.

Now let's look at how event-sourced aggregates work in more detail.

Aggregates in more detail
=========================

Let's define the simplest possible event-sourced aggregate, by
simply subclassing ``Aggregate``.

.. code-block:: python

    from eventsourcing.domain import Aggregate

    class Dog(Aggregate):
        pass


In the usual way with Python classes, we can create a new class instance by
calling the class object.

.. code-block:: python

    dog = Dog()

    assert isinstance(dog, Dog)


Normally when an instance is constructed by calling the class, Python directly
instantiates and initialises the instance. However, when a subclass of ``Aggregate``
is called, firstly an event object is constructed. This event object represents the
fact that the aggregate was "created". Then, this event object is used to construct
and initialise the aggregate instance. The aggregate instance is returned to the
caller of the class.

The new event object is held by the aggregate in an internal list of "pending events". We can
collect pending events from aggregates by calling the aggregate's ``collect_events()`` method,
which is defined on the ``Aggregate`` base class.

.. code-block:: python

    events = dog.collect_events()

    assert len(events) == 1

The event object can be recorded and used to reconstruct the aggregate. To reconstruct the
aggregate, we can simply call the event's ``mutate()`` method.

.. code-block:: python

    copy = events[0].mutate(None)

    assert copy == dog

Using events to determine the state of an aggregate is the essence of
event sourcing. Calling the event's ``mutate()`` method is exactly how
the aggregate object was constructed when the aggregate class was called.

Next, let's talk about aggregate events in more detail.

"Created" events
================

We need to think of suitable names for the particular aggregate events we define
in our domain models. But the general occurrence of creating aggregate objects
requires a general name. The term "created" is used here for this purpose. It
is also adopted as the default name for initial events that represent the
construction and initialisation of an aggregate.

When the ``Dog`` aggregate class above was interpreted by Python, a "created" event
class was automatically defined as a nested class on the aggregate class object.
The name of the "created" event class was given the default name ``'Created'``. And
so the event we collected from the aggregate is an instance of ``Dog.Created``.

.. code-block:: python

    assert isinstance(Dog.Created, type)
    assert isinstance(events[0], Dog.Created)


We can specify an aggregate event class by decorating an aggregate method
with the ``@event`` decorator. The event specified by the decorator will
be triggered when the decorated method is called. This happens by default
for ``__init__()`` methods of aggregate classes. But we can also decorate
an ``__init__()`` method and specify a non-default name for the "created"
event.

Let's redefine the ``Dog`` aggregate class to have an ``__init__()`` method
that takes a ``name`` argument, and initialises a ``name`` attribute with the
given value of the argument. Let's also specify the name of the "created" event
to be ``'Registered'``, by using an ``@event`` decorator on the ``__init__()``
method. The changes are highlighted below.

.. code-block:: python
  :emphasize-lines: 4-6

    from eventsourcing.domain import event

    class Dog(Aggregate):
        @event('Registered')
        def __init__(self, name):
            self.name = name


By specifying the name of the "created" event to be ``'Registered'``, an event
class with this name is defined on the aggregate class.

.. code-block:: python

    assert isinstance(Dog.Registered, type)


"Created" events inherit from the ``Aggregate.Created`` class, which defines a
``mutate()`` method that knows how to construct aggregate instances.

.. code-block:: python

    assert issubclass(Dog.Registered, Aggregate.Created)


As above, we call the ``Dog`` class to create a new aggregate instance.
This time, we need to provide a value for the ``name`` argument.

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
are derived from the signature of the decorated method. Since the
the ``Dog`` aggregate's ``__init__()`` method has a ``name`` argument, so
the "created" event object has a ``name`` attribute.

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
attribute with an empty list. Let's also define a ``add_trick()``
method that appends to this list, and decorate this method with
the ``@event`` decorator, specifying the name of the event to
be ``'TrickAdded'``. The changes are highlighted below.

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


Because the ``add_trick()`` method is decorated with the ``@event`` decorator,
an event class ``Dog.TrickAdded`` is defined on the aggregate class.

.. code-block:: python

    assert isinstance(Dog.TrickAdded, type)

The event will be triggered when the method is called. The
body of the method will be used by the event to mutate the
state of the aggregate object.

Let's create an instance of this ``Dog`` aggregate.

..
    #include-when-testing
..
    import eventsourcing.utils
    eventsourcing.utils._topic_cache.clear()

.. code-block:: python

    dog = Dog('Fido')

As we might expect, the ``name`` of the aggregate object is ``'Fido'``,
and the ``tricks`` attribute is an empty list.

.. code-block:: python

    assert dog.name == 'Fido'
    assert dog.tricks == []

Now let's call ``add_trick()`` with ``'roll over'`` as the argument.

.. code-block:: python

    dog.add_trick('roll over')


As we might expect, the ``tricks`` attribute is now a list with one item, ``'roll over'``.

.. code-block:: python

    assert dog.tricks == ['roll over']

Creating and updating the aggregate caused two events to occur.
We can collect these two events by calling ``collect_events()``.

.. code-block:: python

    events = dog.collect_events()

    assert len(events) == 2

Just like when the ``Dog`` class is called the constructor arguments are used to
create a ``Dog.Registered`` event object, similarly when the ``add_trick()`` method
is called, the values of the method arguments are used to construct a
``Dog.TrickAdded`` event object.

.. code-block:: python

    assert isinstance(events[0], Dog.Registered)
    assert isinstance(events[1], Dog.TrickAdded)

The attributes of the event objects follow from the signatures of the decorated
methods. Just like the "registered" event has a ``name`` attribute, the
"trick added" event has a ``trick`` attribute.

.. code-block:: python

    assert events[0].name == 'Fido'
    assert events[1].trick == 'roll over'

Calling the methods triggers the events, and the events update the aggregate
instance by executing the decorated method body. The resulting state of the
aggregate is the same as if the method were not decorated. The important difference
is that a sequence of events is generated. This sequence of events can be used in
future to reconstruct the current state of the aggregate, as shown below.

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

Define a ``Todos`` aggregate, that has a given ``name`` and a list of ``items``.
Define a method ``add_item()`` that adds a new item to the list. Specify the name
of the "created" event to be ``'Started'`` and the name of the subsequent event
to be ``'ItemAdded'``. Copy the test below and make it pass.

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

* For more information about event-sourced applications, please read
  :doc:`Part 3 </topics/tutorial/part3>` of this tutorial.
* See also the :doc:`the domain module documentation </topics/domain>`.
