=============================================
:mod:`eventsourcing.domain` --- Domain models
=============================================


This module helps with developing event-sourced domain models.

An event-sourced domain model has many event-sourced **aggregates**.
The state of an event-sourced aggregate is determined by a sequence of
**domain events**.
The time needed to reconstruct an aggregate from its domain events can
be reduced by using **snapshots**.

Aggregates in DDD
=================

A design pattern called "aggregate" is described in Eric Evans' book *Domain Driven Design*:

.. pull-quote::

    *"An aggregate is a cluster of associated objects that we treat as a unit
    for the purpose of data changes. Each aggregate has a root and a boundary.*

    *Therefore ... cluster the entities and value objects into aggregates and
    define boundaries around each. Choose one entity to be the root of each
    aggregate, and control all access to the objects inside the boundary
    through the root. Allow external objects to hold references to the
    root only."*

An 'entity' is an object with a fixed unique identity that has variable attributes.
A 'value object' is an object that does not change, and that does not necessarily
have a unique identity. An 'aggregate' is a cluster of such entities and value objects.

The 'root' object of this cluster is an entity, and its identity is used as
to uniquely identity of the aggregate in a domain model. External access to
the state of the aggregate is made through this root entity. The 'aggregate root'
has command and query methods which change and present the state of the aggregate.

The command methods of an event-sourced aggregate trigger domain events, and the
domain events are used to mutate the state of the aggregate. One command may result
in many events. Responding to a single client request may result in the execution of
many commands. The domain events triggered by responding to a client request must be
recorded atomically, and in the order they were created, otherwise the recorded state
of the aggregate could become undesirable, or inconsistent, or unusual, or unworkable.
The atomic recording of the changes to an aggregate defines the 'boundary' mentioned
in the quote above. This boundary is sometimes referred to as the 'consistency boundary'.


Event-sourced aggregates
========================

Event-sourced aggregates are the "enduring objects" of a domain model which enjoy
"adventures of change". An aggregate has a unique identity in the domain model.
For each event-sourced aggregate, there is a sequence of domain events objects.
The state of an event-sourced aggregate is determined by its sequence of domain
event objects. The domain event objects are created by the aggregate's command
methods. The state of an aggregate can change, but the domain event objects do
not change. The "change" in an aggregate is simply the contrast between successive
domain events. The domain event objects are each uniquely identified and have a
serial ordering.

The library's :class:`~eventsourcing.domain.Aggregate` class can be subclassed to develop
event-sourced domain model aggregates.

The method ``_create_()`` is a class method which can be called to create a new
aggregate. The ``_create_()`` method has a required positional argument ``event_class``,
which is used to pass the domain event object class that represents the creation
of the aggregate. The ``_create_()`` method also has a required ``uuid`` argument
which must be a Python ``UUID`` object that will be used to uniquely identify the
aggregate in the domain model. The ``_create_()`` method also accepts arbitrary
keyword-only arguments, which will be used to construct the "created" event object.

The nested class :class:`~eventsourcing.domain.Aggregate.Created` can be subclassed
to define a custom "created" event class for your aggregate. The domain event classes
are defined as a Python frozen data classes. Any keyword arguments passed to the
``_create_()`` method must be matched by corresponding annotations on both the "created"
event class, and the aggregate initializer ``__init__()``.

The method ``_trigger_()`` is an object method which can be called to create new domain
events objects. The ``_trigger_()`` method has a positional argument ``event_class``, which
is used to pass the object type of the new domain event object. The ``_trigger_()``
method also accepts arbitrary keyword-only arguments, which will be used to construct the
domain event object from the given ``event_class``.

The nested class :class:`~eventsourcing.domain.Aggregate.Event` can be subclassed to define
custom domain event object classes, for example the ``SomethingHappened`` class in the example below.
The keyword-only arguments passed to the ``_trigger_()`` method will become the attribute
values of the created domain event object. The domain event classes are defined as Python
frozen data classes. Hence, the keyword-only arguments passed to the ``_trigger_()`` method
will need to be matched by corresponding annotations on your aggregates' domain event class
definitions. For example ``what: str`` on the ``SomethingHappened`` event class in the example
below matches the ``what=what`` keyword argument passed in the call to the ``_trigger_()``
method in the ``make_it_so()`` command.

The method ``_collect_()`` is an object method which can be called to collect the aggregate
domain events that have been triggered but not yet recorded. It is called without any arguments,
and returns a list of all the domain events that have been created by this aggregate since the
previous call to ``_collect_()``.

Domain events
=============

Domain event objects represent decisions by the domain model. Domain events are created
but do not change.

The nested class :class:`~eventsourcing.domain.Aggregate.Event` has attributes ``originator_id``
which is a Python ``UUID``, an ``originator_version`` which is a Python ``int``, and a ``timestamp``
which is a Python ``datetime``.

The nested class :class:`~eventsourcing.domain.Aggregate.Created` extends
:class:`~eventsourcing.domain.Aggregate.Event` and has an attribute ``originator_topic``
which describes the path to the class of an aggregate that has been created.

A "topic" in this library is a string formed from joining together with a colon character
(``':'``) the path to a Python module (e.g. ``'eventsourcing.domain'``) with the qualified
name of an object in that module (e.g. ``'Aggregate.Created'``). For example
``'eventsourcing.domain:Aggregate.Created'`` describes the path to the library's
:class:`~eventsourcing.domain.Aggregate.Created` class. The library's module
``eventsourcing.utils`` contains functions ``resolve_topic()`` and ``get_topic()``
which are used in the library to resolve a given topic to a Python object, and to
construct a topic for a given Python object.

Domain event objects are usually created by aggregate methods, as part of a sequence
that determines the state of an aggregate. The attribute values of new event objects are
determined by these methods. For example, the aggregate's ``_create_()`` method uses
the given value of its ``uuid`` argument as the new event's ``originator_id``. It
sets the ``originator_version`` to the value of ``1``. It derives the ``originator_topic``
value from the concrete aggregate class. And it calls ``datetime.now()`` to create the
``timestamp`` value.

Similarly, the aggregate ``_trigger_()`` method uses the ``uuid`` attribute of the
aggregate as the ``originator_id`` of the new domain event. It uses the current
aggregate ``version`` to create the next version number (by adding ``1``) and uses
this value as the ``originator_version`` of the new domain event. It calls
``datetime.now()`` to create the ``timestamp`` value of the new domain event.

The timestamp values are "timezone aware" datetime objects. The default timezone is
UTC, as defined by Python's ``datetime.timezone.utc``. This default can be changed
either by assigning a ``datetime.tzinfo`` object to the ``TZINFO`` attribute of the
``eventsourcing.domain`` module. The ``TZINFO`` attribute value can also be configured
using environment variables, by setting the environment variable ``TZINFO_TOPIC`` to
a string that describes the "topic" of a ``datetime.tzinfo`` object (for example
``datetime:timezone.utc``).

The :class:`~eventsourcing.domain.Aggregate.Event` has a method ``apply()`` which can
be overridden on custom domain event classes to mutate the state of the aggregate to
which a domain event object pertains. It has an argument ``aggregate`` which is used
to pass the aggregate object to which the domain event object pertains into the ``apply()``
method. The ``apply()`` method is called by the event's ``mutate()`` method, which is
called when reconstructing an aggregate from its events.


Basic example
=============

In the example below, the ``World`` aggregate extends the library's
base class :class:`~eventsourcing.domain.Aggregate`.

The ``create()`` method is a class method that creates and returns
a new ``World`` aggregate object. It uses the ``Created`` event class
as the value of the ``event_class`` argument. It uses a new version 4
``UUID`` object as the value of the ``uuid`` argument.

The ``__init__()`` object initializer method calls the ``super().__init__()``
method with the given ``**kwargs``, and then initialises a
``history`` attribute with an empty Python ``list`` object.

The ``make_it_so()`` method is a command method that triggers
a ``SomethingHappened`` domain event. The event is triggered with the method
argument ``what``.

The custom domain event class ``SomethingHappened`` extends the base class
``Aggregate.Event`` (a Python frozen dataclass) with a field ``what`` which
is defined as a Python ``str``. The ``apply()`` method is implemented to
append the ``what`` value to the aggregate's ``history``.


.. code:: python

    from uuid import uuid4

    from eventsourcing.domain import Aggregate


    class World(Aggregate):
        @classmethod
        def create(cls):
            return cls._create_(
                event_class=cls.Created,
                uuid=uuid4(),
            )

        def __init__(self, **kwargs):
            super(World, self).__init__(**kwargs)
            self.history = []

        def make_it_so(self, what):
            self._trigger_(World.SomethingHappened, what=what)

        class SomethingHappened(Aggregate.Event):
            what: str

            def apply(self, world):
                world.history.append(self.what)


Having defined the aggregate class, we can create a new ``World``
aggregate object by calling the ``World.create()`` class method.

.. code:: python

    # Create new world.
    world = World.create()
    assert isinstance(world, World)

The aggregate's attributes ``created_on`` and ``modified_on`` show
when the aggregate was created and when it was modified. Since there
has only been one domain event, these are initially equal. The values
of these attributes are timezone-aware Python ``datetime`` objects.
These values follow from the ``timestamp`` values of the domain event
objects, and represent when the aggregate's first and last domain events
were created. The timestamps have no consequences for the operation of
the library, and are included to give a general indication to humans of
when the domain events occurred.

.. code:: python

    from datetime import datetime

    assert world.created_on == world.modified_on
    assert isinstance(world.created_on, datetime)


Having created an aggregate object, we can call its methods. The ``World``
aggregate has a command method ``make_it_so()`` which triggers the ``SomethingHappened``
event. The ``mutate()`` method of the ``SomethingHappened`` class appends the ``what``
of the event to the ``history`` of the ``world``. So when we call the ``make_it_so()``
command, the argument ``what`` will be appended to the ``history``. By mutating
the state of the aggregate via triggering domain events, the domain events can
be used to reconstruct the state of the aggregate in future.

.. code:: python

    # Commands methods trigger events.
    world.make_it_so('dinosaurs')
    world.make_it_so('trucks')
    world.make_it_so('internet')

    # State of aggregate object has changed.
    assert world.history[0] == 'dinosaurs'
    assert world.history[1] == 'trucks'
    assert world.history[2] == 'internet'


Now that more than one domain event has been created, the aggregate's
``created_on`` value is less than its ``modified_on`` value.

.. code:: python

    assert world.created_on < world.modified_on


The resulting domain events are now held internally in the aggregate in
a list of pending events, in the ``_pending_events_`` attribute. They can
be collected by calling the ``_collect_()`` method. So far, we have created
four domain events and we have not yet collected them, and so there will be
four pending events: the ``Created`` event, and three ``SomethingHappened``
events.

.. code:: python

    # Has four pending events.
    assert len(world._pending_events_) == 4

    # Collect pending events.
    pending_events = world._collect_()
    assert len(pending_events) == 4
    assert len(world._pending_events_) == 0

    assert isinstance(pending_events[0], Aggregate.Created)
    assert isinstance(pending_events[1], World.SomethingHappened)
    assert isinstance(pending_events[2], World.SomethingHappened)
    assert isinstance(pending_events[3], World.SomethingHappened)
    assert pending_events[1].what == 'dinosaurs'
    assert pending_events[2].what == 'trucks'
    assert pending_events[3].what == 'internet'

    assert pending_events[0].timestamp == world.created_on
    assert pending_events[3].timestamp == world.modified_on


The domain events' ``mutate()`` methods can be used to reconstruct a copy of
the original aggregate object.

.. code:: python

    copy = None
    for domain_event in pending_events:
        copy = domain_event.mutate(copy)

    assert isinstance(copy, World)
    assert copy.uuid == world.uuid
    assert copy.version == world.version
    assert copy.history == world.history
    assert copy.created_on == world.created_on
    assert copy.modified_on == world.modified_on


Snapshots
=========

Snapshots speed up aggregate access time, by avoiding the need to retrieve
and apply all the domain events when reconstructing an aggregate object.

The library's :class:`~eventsourcing.domain.Snapshot` class can be
used to create and restore snapshots of aggregates.

.. code:: python

    from eventsourcing.domain import Snapshot

    snapshot = Snapshot.take(world)

    assert isinstance(snapshot, Snapshot)
    assert snapshot.originator_id == world.uuid
    assert snapshot.originator_version == world.version
    assert snapshot.topic == '__main__:World', snapshot.topic
    assert snapshot.state['history'] == world.history
    assert snapshot.state['created_on'] == world.created_on
    assert snapshot.state['modified_on'] == world.modified_on
    assert len(snapshot.state) == 3


The snapshot's ``mutate()`` method can be used to reconstruct the
aggregate object.

.. code:: python

    copy = snapshot.mutate(None)

    assert isinstance(copy, World)
    assert copy.uuid == world.uuid
    assert copy.version == world.version
    assert copy.history == world.history
    assert copy.created_on == world.created_on
    assert copy.modified_on == world.modified_on

The signature of this method is the same as the aggregate event method
of the same name, so that when reconstructing an aggregate a list that
starts with a snapshot and continues with the subsequent domain events
can be treated in the same way as a list of domain events that starts
with the first aggregate event.


Classes
=======

.. automodule:: eventsourcing.domain
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__
