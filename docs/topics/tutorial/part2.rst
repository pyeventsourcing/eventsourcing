==============================
Tutorial - Part 2 - Aggregates
==============================

In :doc:`Part 1 </topics/tutorial/part1>` we learned
how to write event-sourced aggregates and applications
in Python.

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
fact that the aggregate was "created". This event object is used to construct
and initialise the aggregate instance. The aggregate instance is returned to the
caller of the class.

The new event object is held by the aggregate in an internal list of "pending events". We can
collect pending events from aggregates by calling the aggregate's ``collect_events()`` method,
which is defined on the ``Aggregate`` base class. Calling ``collect_events()`` drains the
internal list of pending events.

.. code-block:: python

    events = dog.collect_events()

    assert len(events) == 1

The "created" event object can be recorded and used to reconstruct the aggregate. To
reconstruct the aggregate, we can simply call the event's ``mutate()`` method.

.. code-block:: python

    copy = events[0].mutate(None)

    assert copy == dog

Using events to determine the state of an aggregate is the essence of
event sourcing. Calling the event's ``mutate()`` method is exactly how
the aggregate object was constructed when the aggregate class was called.

Next, let's talk about aggregate events in more detail.

"Created" events
================

Generally speaking, we need to think of suitably appropriate names for the particular
aggregate events we define in our domain models. But the general occurrence of creating
new aggregates requires a general name. The term "created" is used here for this purpose.
This term is also adopted as the default name for initial events that represent the
construction and initialisation of an aggregate.

When the ``Dog`` aggregate class above was interpreted by Python, a "created" event
class was automatically defined as a nested class on the aggregate class object.
The name of the "created" event class was given the default name ``'Created'``. And
so the event we collected from the aggregate is an instance of ``Dog.Created``.

.. code-block:: python

    assert isinstance(Dog.Created, type)
    assert isinstance(events[0], Dog.Created)


A "created" event class will always be defined for an aggregate class. And a
"created" event object will be triggered when the ``__init__()`` method of an
aggregate is called, which will happen whenever the aggregate class is called.
The attributes of the "created" event class will be defined according to the
``__init__()`` method signature, and the attribute values of the "created"
event object will be set according to the values of the arguments when the
``__init__()`` method is called, which are usually the values of the arguments
when the aggregate class is called. The body of the ``__init__()`` method will
be used to initialise the aggregate object.

By default, the "created" event class will have the name ``'Created'``.
But we can explicitly specify a name for the "created" event by decorating the
``__init__()`` method with the ``@event`` decorator.

Let's redefine the ``Dog`` aggregate class to have an ``__init__()`` method
that is decorated with the ``@event`` decorator. Let's specify the name of
the "created" event to be ``'Registered'``. Let's also define the ``__init__()``
method signature to have a ``name`` argument, and a method body that initialises
a ``name`` attribute with the given value of the argument. The changes are
highlighted below.

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


All "created" events inherit from the ``Aggregate.Created`` class, which defines
a ``mutate()`` method that knows how to construct aggregate instances.

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


As we might expect, the given ``name`` was used to initialise the ``name``
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

Note what's happening there.  We start with ``None`` and end up with an instance of ``Dog`` that
has the same state as the original ``dog`` object.  Note also that ``dog`` and ``copy`` are different objects
with the same type and state, not two references to the same Python object.

.. code-block:: python

    assert copy.name == 'Fido'
    assert id(copy) != id(dog)


We have specified an aggregate event class by decorating an aggregate method
with the ``@event`` decorator. The event specified by the decorator was
triggered when the decorated method was called.


Subsequent events
=================

We can take this further by defining a second method that will be used
to change the aggregate object after it has been created.

Let's firstly adjust the ``__init__()`` to initialise a ``tricks``
attribute with an empty list. Let's also define an ``add_trick()``
method that appends to this list. Let's also decorate ``add_trick()``
with the ``@event`` decorator, specifying the name of the event to
be ``'TrickAdded'``. The changes are highlighted below.

.. code-block:: python
    :emphasize-lines: 5,7-9

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

When the ``Dog`` class is called a ``Dog.Registered`` event object was created.
Similarly, when the ``add_trick()`` method was called, a ``Dog.TrickAdded`` event
object was created.

.. code-block:: python

    assert isinstance(events[0], Dog.Registered)
    assert isinstance(events[1], Dog.TrickAdded)

The signatures of the decorated methods are used to define the event classes.
And the values of the method arguments are used to instantiate the event objects.

And so, just like the "registered" event has a ``name`` attribute, the
"trick added" event has a ``trick`` attribute. The values of these attributes
are the values that were given when the methods were called.

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

Explicit style
==============

Sometimes you may wish to define aggregate event classes explicitly.

One reason for defining explicit event classes is to code for model changes.
The version of the event class can be defined along with :ref:`upcast methods <Versioning>`
that adjust stored events created at previous versions.

The example below shows the ``Dog`` aggregate class defined using explicit
event classes.

.. code-block:: python

    class Dog(Aggregate):
        class Registered(Aggregate.Created):
            name: str

        @event(Registered)
        def __init__(self, name):
            self.name = name
            self.tricks = []

        class TrickAdded(Aggregate.Event):
            trick: str

        @event(TrickAdded)
        def add_trick(self, trick):
            self.tricks.append(trick)


The ``Dog.Registered`` class inherits ``Aggregate.Created`` event class.
The ``Dog.TrickAdded`` class inherits base ``Aggregate.Event`` class.
The ``@event`` decorator is used to specify the event class
that will be triggered when the decorated method is called.

..
    #include-when-testing
..
    import eventsourcing.utils
    eventsourcing.utils._topic_cache.clear()

.. code-block:: python

    # Check the command and query methods.
    dog = Dog('Fido')
    assert dog.name == 'Fido'
    assert dog.tricks == []
    dog.add_trick('roll over')
    assert dog.tricks == ['roll over']

    # Check reconstruction of aggregate state.
    copy = None
    for e in dog.collect_events():
        copy = e.mutate(copy)
    assert copy == dog


Sometimes you will need the command method to do some work before the event
is triggered.

If an aggregate command method needs to do some work on its arguments before
triggering an event, the ``@event`` decorator can be used on a "private" method
that is called by the "public" command method after the work has been done.

The example below shows a ``Dog`` aggregate class with an undecorated "public"
command method ``add_trick()`` that call a decorated "private" method ``_add_trick()``.

.. code-block:: python

    class Dog(Aggregate):
        def __init__(self, name):
            self.name = name
            self.tricks = []

        def add_trick(self, trick):
            # Do some work.
            assert isinstance(trick, str)
            # Trigger event.
            self._add_trick(trick)

        class TrickAdded(Aggregate.Event):
            trick: str

        @event(TrickAdded)
        def _add_trick(self, trick):
            self.tricks.append(trick)


Because the ``trick_added()`` method is not decorated with the ``@event``
decorator, it does not trigger an event when it is called. Instead, the
event is triggered when the ``_trick_added()`` method is called.

..
    #include-when-testing
..
    import eventsourcing.utils
    eventsourcing.utils._topic_cache.clear()

.. code-block:: python

    # Check the command and query methods.
    dog = Dog('Fido')
    assert dog.name == 'Fido'
    assert dog.tricks == []
    dog.add_trick('roll over')
    assert dog.tricks == ['roll over']

    # Check the 'assert isinstance' statement.
    try:
        dog.add_trick(101)
    except AssertionError:
        assert dog.tricks == ['roll over']
    else:
        raise AssertionError("Shouldn't get here")

    # Check reconstruction of aggregate state.
    copy = None
    for e in dog.collect_events():
        copy = e.mutate(copy)
    assert copy == dog


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
