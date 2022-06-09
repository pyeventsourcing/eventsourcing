==============================
Tutorial - Part 2 - Aggregates
==============================

In :doc:`Part 1 </topics/tutorial/part1>` we learned
how to write event-sourced aggregates and applications
in Python.

Now let's look at how event-sourced aggregates work in more detail.

Aggregates in more detail
=========================

We can define event-sourced aggregates with the library's ``Aggregate`` class
and ``@event`` decorator.

.. code-block:: python

    from eventsourcing.domain import Aggregate, event

Let's define the simplest possible event-sourced aggregate, by
simply subclassing ``Aggregate``.

.. code-block:: python

    class Dog(Aggregate):
        def __init__(self):
            pass


In the usual way with Python classes, we can create a new instance by
calling the class.

.. code-block:: python

    dog = Dog()

    assert isinstance(dog, Dog)


The ``dog`` aggregate has an ``id`` attribute. The ID is used to uniquely identify
the aggregate within a collection of aggregates. It happens to be a UUID.

.. code-block:: python

    from uuid import UUID

    assert isinstance(dog.id, UUID)


Normally when an instance is constructed by calling the class, Python directly
constructs the instance. However, when a subclass of ``Aggregate`` is called,
firstly an event object is constructed. This event object represents the
fact that the aggregate was "created". This event object is used to construct
the aggregate instance. The aggregate instance is returned to the caller of the
class.

The event object is held by the aggregate in an internal list of "pending events".
We can collect pending events from aggregates by calling the aggregate's
``collect_events()`` method, which is defined on the ``Aggregate`` base
class.

.. code-block:: python

    events = dog.collect_events()

    assert len(events) == 1

The "created" event object can be used to reconstruct the aggregate.

To reconstruct the aggregate from the event, we can call the event's ``mutate()``
method.

.. code-block:: python

    copy = events[0].mutate(None)

    assert copy.id == dog.id

Using events to determine the state of an aggregate is the essence of event
sourcing.

Next, let's talk about aggregate events in more detail.

"Created" events
================

When the ``Dog`` aggregate code is interpreted by Python, a "created" event
class is automatically defined for the aggregate. The event class is defined
as a nested class.

By default, the name of the "created" event class is ``'Created'``. And
so the event we collected from the aggregate is an instance of ``Dog.Created``.

.. code-block:: python

    assert isinstance(Dog.Created, type)
    assert isinstance(events[0], Dog.Created)


We can specify a name for the "created" event class by using the ``@event``
decorator on the aggregate's ``__init__()`` method.

Let's specify the name of the "created" event class to be ``'Registered'``.
The changes are highlighted below.

..
    #include-when-testing
..
    import eventsourcing.utils
    eventsourcing.utils._topic_cache.clear()

.. code-block:: python
  :emphasize-lines: 2

    class Dog(Aggregate):
        @event('Registered')
        def __init__(self):
            pass

We can see the ``Dog`` class has a nested class ``Dog.Registered``.

.. code-block:: python

    assert isinstance(Dog.Registered, type)

Now, after we call the aggregate class, a ``Dog.Registered``
event is collected from the aggregate instance.

.. code-block:: python

    dog = Dog()
    events = dog.collect_events()

    assert len(events) == 1
    assert isinstance(events[0], Dog.Registered)


Let's adjust the ``__init__()`` method to accept a ``name``
argument, and to initialise a ``name`` attribute with the
given value of the argument. The changes are highlighted below.

.. code-block:: python
  :emphasize-lines: 3-4

    class Dog(Aggregate):
        @event('Registered')
        def __init__(self, name):
            self.name = name

Now, when we call the ``Dog`` class, we need to provide a value for
the ``name`` argument.

..
    #include-when-testing
..
    import eventsourcing.utils
    eventsourcing.utils._topic_cache.clear()

.. code-block:: python

    dog = Dog(name='Fido')


When the aggregate class is called, a "created" event object is
constructed and used to to construct an aggregate object.
The body of the ``__init__()`` method is used by the "created" event object
to initialise the aggregate instance. The result is the aggregate instance's
``name`` attribute has the value given when calling the aggregate class.

We can see the aggregate instance ``dog`` has an attribute ``name``, which
has the value given when calling the aggregate class.

.. code-block:: python

    assert dog.name == 'Fido'


We can call ``collect_events()`` to get the "created" event from
the aggregate object.

.. code-block:: python

    events = dog.collect_events()

    assert len(events) == 1

We can see the event object is an instance of the class ``Dog.Registered``.

.. code-block:: python

    assert isinstance(events[0], Dog.Registered)

The event class ``Dog.Registered`` is a subclass of the base class ``Aggregate.Created``.

.. code-block:: python

    assert issubclass(Dog.Registered, Aggregate.Created)


Event classes defined by the ``@event`` decorator match the decorated
method signature. Each parameter of the method signature will be matched by an
event object attribute. Since the ``__init__()`` method signature has
a ``name`` argument, so the "created" event has a ``name`` attribute.

We can see the "created" event object has a ``name`` attribute, which has the
value given when calling the aggregate class, and which is the value that was used
when initialising the aggregate instance.

.. code-block:: python

    assert events[0].name == 'Fido'

The construction of the aggregate instance is mediated by the "created" event
object, so that we can store the event object in a database, and so that the aggregate
instance can be reconstructed in future from stored events.

The "created" event object can be used to construct another object with the
same state as the original aggregate object. That is, it can be used to
reconstruct the initial current state of the aggregate.

.. code-block:: python

    copy = events[0].mutate(None)

    assert copy.id == dog.id
    assert copy.name == dog.name

Note what's happening when we call ``mutate()``. We start with ``None`` and
end up with an instance of ``Dog`` that has the same state as the original
``dog`` object. Note also that ``dog`` and ``copy`` are different objects
with the same type and state, not two references to the same Python object.

.. code-block:: python

    assert id(copy) != id(dog)


In this section, we specified a "created" event class by decorating the
``__init__()`` method of an aggregate class with the ``@event`` decorator.
When the aggregate class was called, a "created" event object was constructed
and used to construct an aggregate instance. The "created" event object
was used to reconstruct the state of the aggregate.

We can take this further by defining aggregate methods that will
change the state of aggregate instances by triggering subsequent
events.


Subsequent events
=================

We can define aggregate methods that change the state of an aggregate instance
after it has been created.

Let's continue to develop the ``Dog`` class, by defining an ``add_trick()``
method. This method appends a given ``trick`` to a list of tricks that
a dog has been trained to perform. This method is decorated with ``@event``
decorator, so that an event object will be constructed when the method is
called. The event object will use the method body to change the state of
the aggregate. The name of the event class is specified to be ``'TrickAdded'``.
We also need to adjust the ``__init__()`` method, to initialise a ``tricks``
attribute with an empty list. The changes are highlighted below.

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


The event class ``Dog.TrickAdded`` is a subclass of the base class ``Aggregate.Event``.

.. code-block:: python

    assert issubclass(Dog.TrickAdded, Aggregate.Event)


Let's create an instance of this ``Dog`` aggregate.

..
    #include-when-testing
..
    import eventsourcing.utils
    eventsourcing.utils._topic_cache.clear()

.. code-block:: python

    dog = Dog(name='Fido')

As we might expect, the ``name`` is ``'Fido'``,
and ``tricks`` is an empty list.

.. code-block:: python

    assert dog.name == 'Fido'
    assert dog.tricks == []

Now let's call ``add_trick()`` with ``'roll over'`` as the argument.

.. code-block:: python

    dog.add_trick(trick='roll over')


The ``tricks`` attribute is now a list with one item, ``'roll over'``.

.. code-block:: python

    assert dog.tricks == ['roll over']

Creating and updating the aggregate caused two events to occur.
We can collect these two events by calling ``collect_events()``.

.. code-block:: python

    events = dog.collect_events()

    assert len(events) == 2

A ``Dog.Registered`` event object was constructed when the ``Dog`` class
was called. And a ``Dog.TrickAdded`` event object was constructed when
the ``add_trick()`` method was called.

.. code-block:: python

    assert isinstance(events[0], Dog.Registered)
    assert isinstance(events[1], Dog.TrickAdded)

The signatures of the decorated methods are used to define event classes.
When the method is called, the values of the method arguments are used to
construct an event object.

We can see the ``Dog.Registered`` event has a ``name`` attribute and the
``Dog.TrickAdded`` event has a ``trick`` attribute. The values of these
attributes are the values that were given when the methods were called.

.. code-block:: python

    assert events[0].name == 'Fido'
    assert events[1].trick == 'roll over'

Calling a method constructs an event. The event updates the aggregate by
executing the decorated method body. The resulting state of the aggregate
is the same as if the method were not decorated. The important difference
is that a sequence of events is generated. This sequence of events can be
used in future to reconstruct the current state of the aggregate, as shown
below.

.. code-block:: python

    copy = None
    for e in events:
        copy = e.mutate(copy)

    assert copy.id == dog.id
    assert copy.name == dog.name
    assert copy.tricks == dog.tricks

You can try all of this for yourself by copying the code snippets above.

Explicit style
==============

You may prefer to define aggregate event classes explicitly.

The example below shows the ``Dog`` aggregate class defined with explicit
event classes. The ``@event`` decorator is used to specify the event class
that will be triggered when the decorated method is called.

The ``Dog.Registered`` class inherits ``Aggregate.Created``
event class. It has a ``name`` attribute which matches the ``name`` argument
of the ``__init__()`` method.

The ``Dog.TrickAdded`` class inherits ``Aggregate.Event``
class. It has a ``trick`` attribute which matches the ``trick`` argument of
the ``add_trick()`` method.

The event class definitions are interpreted as `Python dataclasses <https://docs.python.org/3/library/dataclasses.html>`_.

.. code-block:: python
    :emphasize-lines: 2,3,5,10,11,13

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


The important things to remember are:

* the ``@event`` decorator specifies the event class itself,
* the "created" event class must be a subclass of ``Aggregate.Created``,
* subsequent event classes must be subclasses of ``Aggregate.Event``, and
* the event class attributes must match the decorated method arguments.

We can use the aggregate class in the same way.

..
    #include-when-testing
..
    import eventsourcing.utils
    eventsourcing.utils._topic_cache.clear()

.. code-block:: python

    # Create a dog.
    dog = Dog(name='Fido')

    assert dog.name == 'Fido'
    assert dog.tricks == []

    # Add trick.
    dog.add_trick(trick='roll over')

    assert dog.tricks == ['roll over']

    # Reconstruct aggregate from events.
    copy = None
    for e in dog.collect_events():
        copy = e.mutate(copy)

    assert copy.id == dog.id
    assert copy.name == dog.name
    assert copy.tricks == dog.tricks

One reason for defining event classes explicitly is to be explicit about
the event classes, as a matter of style. Another reason is versioning of
the event class (see :ref:`Versioning <Versioning>`).

Decorating private methods
==========================

Sometimes you will need the command method to do some work before the event
is triggered.

If an aggregate command method needs to do some work on its arguments before
triggering an event, the ``@event`` decorator can be used on a "private" method
that is called by the "public" command method after the work has been done. The
"private" method can have a completely different method signature from the "public"
method.

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
            self._add_trick(trick=trick)

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

    # Create a dog.
    dog = Dog(name='Fido')
    assert dog.name == 'Fido'
    assert dog.tricks == []

    # Add trick.
    dog.add_trick(trick='roll over')
    assert dog.tricks == ['roll over']

    # Add trick - wrong type of argument.
    try:
        dog.add_trick(trick=101)
    except AssertionError:
        assert dog.tricks == ['roll over']
    else:
        raise AssertionError("Shouldn't get here")

    # Reconstruct aggregate from events.
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

* For more information about event-sourced aggregates, please read the :doc:`the domain module documentation </topics/domain>`.
* For more information about event-sourced applications, please read
  :doc:`Part 3 </topics/tutorial/part3>` of this tutorial.
