==============================================
:mod:`~eventsourcing.domain` --- Domain models
==============================================


This module helps with developing event-sourced domain models.

An event-sourced domain model has many event-sourced **aggregates**.
The state of an event-sourced aggregate is determined by a sequence of
**domain events**.
The time needed to reconstruct an aggregate from its domain events can
be reduced by using **snapshots**.


Aggregates in DDD
=================

Aggregates are enduring objects which enjoy adventures of change. The
book *Domain-Driven Design* by Eric Evans' describes a design pattern
called "aggregate" in the following way.

.. pull-quote::

    *"An aggregate is a cluster of associated objects that we treat as a unit
    for the purpose of data changes. Each aggregate has a root and a boundary...*

    *Therefore...*

    *Cluster the entities and value objects into aggregates and
    define boundaries around each. Choose one entity to be the root of each
    aggregate, and control all access to the objects inside the boundary
    through the root. Allow external objects to hold references to the
    root only."*

An aggregate is a cluster of 'entities' and 'value objects'. An entity is an
object with a fixed unique identity and other attributes that may vary. A
value object has attributes that do not vary, and does not necessarily have
a unique identity. This basic notion of a cluster of software objects is
understandable as straightforward `object-oriented programming
<https://en.wikipedia.org/wiki/Object-oriented_programming>`_.

An aggregate has a 'root'. The 'root' of an aggregate is an entity, and its
identity is used to uniquely identify the cluster of objects in a domain model.
This entity is known as the 'root entity' or the 'aggregate root'. External
references to the cluster of objects use the ID of the root entity. Access
to the cluster of objects is made through the root entity.

Changes to the cluster of objects are made using 'command methods' defined on
the root entity, and the state of the cluster of objects is obtained by using
either 'query methods' or properties of the root entity. The idea of distinguishing
between command methods (methods that change state but do not return values) and
query methods (methods that return values but do not change state) is known as
'command-query separation' or CQS. `CQS was devised by Bertrand Meyer
<https://en.wikipedia.org/wiki/Command%E2%80%93query_separation>`_ and
described in his book *Object Oriented Software Construction*.

The 'boundary' of the aggregate is defined by the extent of the cluster of objects.
The 'consistency' of the cluster of objects is maintaining by making sure all
the changes that result from a single command are `recorded atomically
<https://en.wikipedia.org/wiki/Atomicity_(database_systems)>`_. There is
only ever one cluster of objects for any given aggregate, so there is
no branching, and the atomic changes have a serial order. These two notions
of 'consistency' and 'boundary' are combined in the notion in *Domain-Driven
Design* of 'consistency boundary'. Whilst we can recognise the cluster of objects as
basic object-orientated programming, and we can recognise the use of command and
query methods as the more refined pattern called CQS, the 'consistency boundary'
notion gives to the aggregates in *Domain-Driven Design* their distinctive character.


.. _Aggregates:

Event-sourced aggregates
========================

It is in the `Zen of Python <https://www.python.org/dev/peps/pep-0020/>`_ that
explicit is better than implicit. The changes to an aggregate's
cluster of objects will always follow from decisions made by the aggregate, but these
decisions had not been directly expressed as objects. It will always be true that
a decision itself does not change, but this fact had not been directly expressed.

.. pull-quote::

    *"Explicit is better than implicit."*


To make things explicit, the decisions made in the command methods of an
aggregate can be coded and recorded as a sequence of immutable 'domain event'
objects, and this sequence can be used to evolve the aggregate's cluster of
entities and value objects. Event-sourced aggregates make these things explicit.
For each event-sourced aggregate, there is a sequence of domain event objects,
and the state of an event-sourced aggregate is determined by its sequence of
domain event objects. The state of an aggregate can change, and its sequence
of domain events can be augmented. But once created the individual domain
event objects do not change. They are what they are. The notion of 'change'
is the contrast between successive domain events in an aggregate's sequence
(contrasted from the standpoint of the cluster of objects within an aggregate's consistency
boundary, which is a standpoint that may change since there must be a function
that applies the events to the cluster, and this function can be adjusted.
Hence it isn't strictly true to say that the state of an aggregate is determined
by a sequence of events. The events merely contribute determination, and the
state is in fact determined by a combination of the sequence of events and
a function that constructs that state from those events, but I digress...)

The state of an aggregate, event-sourced or not, is changed by calling its
command methods. In an event-sourced aggregate, the command methods create
new domain event objects. The domain events are used to evolve the state of
the aggregate. By evolving the state of the aggregate via creating and applying
domain events, the domain events can be recorded and used in future to reconstruct
the state of the aggregate.

One command may result in many new domain event objects, and a single client request may
result in the execution of many commands. To maintain consistency in the domain model,
all the domain events triggered by responding to a single client request must be recorded
atomically in the order they were created, otherwise the recorded state of the aggregate
may become inconsistent with respect to that which was desired or expected.

Aggregate base class
--------------------

This library's :class:`~eventsourcing.domain.Aggregate` class is a base class for event-sourced
aggregates. It can be imported from the library's :mod:`eventsourcing.domain` module.

.. code:: python

    from eventsourcing.domain import Aggregate


The :class:`~eventsourcing.domain.Aggregate` base class can be used to develop
event-sourced aggregates. See for example the ``World`` aggregate in the
:ref:`basic example <Aggregate basic example>` below.
The :class:`~eventsourcing.domain.Aggregate` base class has three methods which can
be used by subclasses:

* the "private" class method :func:`~eventsourcing.domain.Aggregate._create`
  which is used to create aggregate objects;

* the "private" object method :func:`~eventsourcing.domain.Aggregate._trigger_event`
  which is used to trigger subsequent events; and

* the "public" object method :func:`~eventsourcing.domain.Aggregate.collect_events`
  which is used to collect aggregate events.

These methods are explained below.


Creating new aggregates
-----------------------

Firstly, the :class:`~eventsourcing.domain.Aggregate` class has a "private" class
method :func:`~eventsourcing.domain.Aggregate._create` which can be used to create
a new aggregate. It works by creating the first of a new sequence of domain
event objects, and uses this domain event object to construct and initialise
an instance of the aggregate class. Usually, this "private" method will be called
by a "public" class method defined on a subclass of the :class:`~eventsourcing.domain.Aggregate`
base class. For example, see the class method ``create()`` of the :class:`World`
aggregate class in the :ref:`basic example <Aggregate basic example>` below.

The :func:`~eventsourcing.domain.Aggregate._create` method has a required positional
argument ``event_class`` which is used by the caller to pass a domain event class that
will represent the fact that an aggregate was "created". A domain event object of this
type will be constructed by this method, and this domain event object will be used to
construct and initialise an aggregate object. This method will then return that aggregate
object. The :func:`~eventsourcing.domain.Aggregate._create` method also has
a required ``id`` argument which should be a Python :class:`~uuid.UUID`
object that will be used to uniquely identify the aggregate in the domain
model.

.. code:: python

    from uuid import uuid4

    aggregate_id = uuid4()

    aggregate = Aggregate._create(Aggregate.Created, id=aggregate_id)

The library's :class:`~eventsourcing.domain.Aggregate` base class is defined with
a nested class :class:`~eventsourcing.domain.Aggregate.Created` which
can be used to represent the fact that an aggregate was "created". The
:class:`~eventsourcing.domain.Aggregate.Created` class is defined as a
`frozen Python data class <https://docs.python.org/3/library/dataclasses.html>`_
with four attributes: the ID of an aggregate, a version number, a timestamp,
and the :ref:`topic <Topics>` of an aggregate class --- see
the :ref:`Domain events <Events>`
section below for more information. Except
for the ID which is passed as the ``id`` argument to the
:func:`~eventsourcing.domain.Aggregate._create` method,
the values of these other attributes are worked out by the
:func:`~eventsourcing.domain.Aggregate._create` method. The
:class:`~eventsourcing.domain.Aggregate.Created` class can
be used directly, but is normally subclassed to define a particular "created"
event class for a particular aggregate class, with a suitable name and
with suitable extra attributes that represent the particular beginning
of a particular type of aggregate. A "created" event class should be named using a past
participle that describes the beginning of something, such as "Started",
"Opened", or indeed "Created".

The :func:`~eventsourcing.domain.Aggregate._create` method also accepts arbitrary
keyword-only arguments, which if given will also be used to construct the event object
in addition to those mentioned above. The "created" event object will be constructed with these
additional arguments, and so the extra method arguments must be matched by the attributes of the
"created" event class. (The concrete aggregate class's initializer method :func:`__init__`
should also be coded to accept these extra arguments.)

Having been created, an aggregate object will have an aggregate ID. The ID is presented
by its :py:obj:`~eventsourcing.domain.Aggregate.id` property. The ID will be identical to
the value passed with the ``id`` argument to the :func:`~eventsourcing.domain.Aggregate._create`
method.

.. code:: python

    assert aggregate.id == aggregate_id


A new aggregate instance has a version number. The version number is presented by its
:py:obj:`~eventsourcing.domain.Aggregate.version` property, and is a Python :class:`int`.
The initial version of a newly created aggregate is always 1.

.. code:: python

    assert aggregate.version == 1


A new aggregate instance has a :py:obj:`~eventsourcing.domain.Aggregate.created_on`
property which gives the date and time when an aggregate object was created, and is determined
by the timestamp attribute of the first event in the aggregate's sequence, which is the "created"
event. It is a Python :class:`~datetime.datetime` object.

.. code:: python

    from datetime import datetime

    assert isinstance(aggregate.created_on, datetime)


A new aggregate instance also has a :py:obj:`~eventsourcing.domain.Aggregate.modified_on`
property which gives the date and time when an aggregate object was last modified, and is determined
by the timestamp attribute of the last event in the aggregate's sequence. It is also a Python
:class:`~datetime.datetime` object.

.. code:: python

    from datetime import datetime

    assert isinstance(aggregate.modified_on, datetime)

Initially, since there is only one event in the aggregate's sequence, the ``created_on``
and ``modified_on`` values are identical, and equal to the timestamp of the "created" event.

.. code:: python

    assert aggregate.created_on == aggregate.modified_on


Triggering subsequent events
----------------------------

Secondly, the :class:`~eventsourcing.domain.Aggregate` class has a "private" object
method :func:`~eventsourcing.domain.Aggregate._trigger_event` which can be called
to create subsequent aggregate event objects and apply them to the aggregate.
This method is usually called by the command methods of an aggregate to
express the decisions that it makes. For example,
see the ``make_it_so()`` method of the ``World`` class in the :ref:`basic example
<Aggregate basic example>` below.

The :func:`~eventsourcing.domain.Aggregate._trigger_event` method has a positional
argument ``event_class``, which is used to pass the type of aggregate event to be
triggered.

.. code:: python

    aggregate._trigger_event(Aggregate.Event)

The :class:`~eventsourcing.domain.Aggregate` class has a nested
:class:`~eventsourcing.domain.Aggregate.Event` class. It is defined
as a `frozen Python data class <https://docs.python.org/3/library/dataclasses.html>`_
with three attributes: the ID of an aggregate, a version number, and a timestamp.
It can be used as a base class to define aggregate event classes. The
:class:`~eventsourcing.domain.Aggregate.Created` event class discussed above is a
subclass of :class:`~eventsourcing.domain.Aggregate.Event`. For another example, see
the ``SomethingHappened`` class in the :ref:`basic example <Aggregate basic example>`
below. Aggregate event classes are usually named using past participles to describe
what was decided by the command method, such as "Done", "Updated", "Closed", etc.
See the :ref:`Domain events <Events>` section below for more information about
aggregate event classes. They can be defined on aggregate classes as nested classes.

The :func:`~eventsourcing.domain.Aggregate._trigger_event` method also accepts arbitrary
keyword-only arguments, which will be used to construct the aggregate event object. As with the
:func:`~eventsourcing.domain.Aggregate._create` method described above, the event object will be constructed
with these arguments, and so any extra arguments must be matched by the expected values of
the event class. For example ``what: str`` on the ``SomethingHappened`` event class in the
:ref:`basic example <Aggregate basic example>` below matches the ``what=what`` keyword
argument passed in the call to the :func:`~eventsourcing.domain.Aggregate._trigger_event`
method in the ``make_it_so()`` command.

The ``version`` will be incremented by 1 for each event that is triggered.

.. code:: python

    assert aggregate.version == 2


After triggering a second event, the modified time will be greater than the created time.

.. code:: python

    assert aggregate.modified_on > aggregate.created_on

The timestamps have no consequences for the operation of the library. The aggregate
events objects are ordered in their sequence by their version numbers, and not by
their timestamps. The timestamps exist only to give a general indication to
humans of when things occurred.


Collecting pending events
-------------------------

Thirdly, the :class:`~eventsourcing.domain.Aggregate` class has a "public" object method
:func:`~eventsourcing.domain.Aggregate.collect_events`
which can be called to collect the aggregate events that have been created but
since either the last call to this method or since the aggregate object was
constructed. This method is called without any arguments.

.. code:: python

    pending_events = aggregate.collect_events()

    assert len(pending_events) == 2

    assert isinstance(pending_events[0], Aggregate.Created)
    assert pending_events[0].originator_id == aggregate.id
    assert pending_events[0].originator_version == 1
    assert pending_events[0].timestamp == aggregate.created_on

    assert isinstance(pending_events[1], Aggregate.Event)
    assert pending_events[1].originator_id == aggregate.id
    assert pending_events[1].originator_version == 2
    assert pending_events[1].timestamp == aggregate.modified_on


.. _Aggregate basic example:

Basic example
=============

In the example below, the ``World`` aggregate is a subclass of the library's
base :class:`~eventsourcing.domain.Aggregate` class. The ``__init__()`` method
extends the super class method and initialises a ``history`` attribute with an
empty Python ``list`` object.

The ``create()`` method is a class method that creates and returns
a new ``World`` aggregate object. It calls the base class
:func:`~eventsourcing.domain.Aggregate._create` method. It
uses its ``Created`` event class as the value of the ``event_class``
argument. It uses a
`version 4 UUID <https://en.wikipedia.org/wiki/Universally_unique_identifier#Version_4_(random)>`_
object as the value of the ``id`` argument. (See the :ref:`Namespaced IDs <Namespaced IDs>`
section below for a discussion about using version 5 UUIDs.)

The ``make_it_so()`` method is a command method that triggers
a ``World.SomethingHappened`` domain event. It calls the base class
:func:`~eventsourcing.domain.Aggregate._trigger_event` method.
The event is triggered with the method argument ``what``.

.. code:: python

    from dataclasses import dataclass

    from eventsourcing.domain import Aggregate


    class World(Aggregate):
        def __init__(self, **kwargs):
            super(World, self).__init__(**kwargs)
            self.history = []

        @classmethod
        def create(cls):
            return cls._create(cls.Created, id=uuid4())

        @dataclass(frozen=True)
        class Created(Aggregate.Created):
            pass

        def make_it_so(self, what):
            self._trigger_event(self.SomethingHappened, what=what)

        @dataclass(frozen=True)
        class SomethingHappened(Aggregate.Event):
            what: str

            def apply(self, world):
                world.history.append(self.what)


The nested ``Created`` class is defined as a subclass of the base aggregate
:class:`~eventsourcing.domain.Aggregate.Created` class. Although in
this simple example this ``World.Created`` event class carries no more
attributes than the base class event that it inherits, it's always worth
defining all event classes on the concrete aggregate class itself in case
these classes need to be modified so that old instances can be upcast to
new versions (see :ref:`Versioning <Versioning>`). The name of an event class
should express your project's ubiquitous language, take the grammatical
form of a past participle (either regular or irregular), and describe the
type of decision represented by the event class.

The nested ``SomethingHappened`` class is a frozen data class that extends the
base aggregate event class ``Aggregate.Event`` (also a frozen data class) with a
field ``what`` which is defined as a Python :class:`str`. An ``apply()`` method
is defined which appends the ``what`` value to the aggregate's ``history``. This
method is called when the event is triggered (see :ref:`Domain events <Events>`).

By defining the event class under the command method which triggers it, and then
defining an apply() method as part of the event class definition, the story of
calling a command method, triggering an event, and evolving the state of the aggregate
is expressed neatly in three parts.

Having defined the ``World`` aggregate class, we can create a new ``World``
aggregate object by calling the ``World.create()`` class method.

.. code:: python

    world = World.create()

    assert isinstance(world, World)

The aggregate's attributes ``created_on`` and ``modified_on`` show
when the aggregate was created and when it was modified. Since there
has only been one domain event, these are initially equal. The values
of these attributes are timezone-aware Python :class:`~datetime.datetime` objects.
These values follow from the ``timestamp`` values of the domain event
objects, and represent when the aggregate's first and last domain events
were created. The timestamps have no consequences for the operation of
the library, and are included to give a general indication to humans of
when the domain events occurred.

.. code:: python

    from datetime import datetime

    assert world.created_on == world.modified_on
    assert isinstance(world.created_on, datetime)


We can call the aggregate object methods. The ``World`` aggregate has a command
method ``make_it_so()`` which triggers the ``SomethingHappened`` event. The
``apply()`` method of the ``SomethingHappened`` class appends the ``what``
of the event to the ``history`` of the ``world``. So when we call the ``make_it_so()``
command, the argument ``what`` will be appended to the ``history``.

.. code:: python

    # Commands methods trigger events.
    world.make_it_so("dinosaurs")
    world.make_it_so("trucks")
    world.make_it_so("internet")

    # State of aggregate object has changed.
    assert world.history[0] == "dinosaurs"
    assert world.history[1] == "trucks"
    assert world.history[2] == "internet"


Now that more than one domain event has been created, the aggregate's
``modified_on`` value is greater than its ``created_on`` value.

.. code:: python

    assert world.modified_on > world.created_on


The resulting domain events are now held internally in the aggregate in
a list of pending events, in the ``_pending_events`` attribute. The pending
events can be collected by calling the aggregate's
:func:`~eventsourcing.domain.Aggregate.collect_events` method. These events are
pending to be saved, and indeed the library's :ref:`application <Application objects>`
object has a :func:`~eventsourcing.application.Application.save` method which works by
calling this method. So far, we have created four domain events and we have
not yet collected them, and so there will be four pending events: one ``Created``
event, and three ``SomethingHappened`` events.

.. code:: python

    # Has four pending events.
    assert len(world._pending_events) == 4

    # Collect pending events.
    pending_events = world.collect_events()
    assert len(pending_events) == 4
    assert len(world._pending_events) == 0

    assert isinstance(pending_events[0], World.Created)
    assert isinstance(pending_events[1], World.SomethingHappened)
    assert isinstance(pending_events[2], World.SomethingHappened)
    assert isinstance(pending_events[3], World.SomethingHappened)
    assert pending_events[1].what == "dinosaurs"
    assert pending_events[2].what == "trucks"
    assert pending_events[3].what == "internet"

    assert pending_events[0].timestamp == world.created_on
    assert pending_events[3].timestamp == world.modified_on


.. _Events:

Domain events
=============

Domain events are created but do not change.

The base class :class:`~eventsourcing.domain.DomainEvent` is defined as a
frozen data class with an ``originator_id`` attribute which is a Python
:class:`~uuid.UUID` that holds an aggregate ID, an ``originator_version``
attribute which is a Python :class:`int` that holds the version of an
aggregate, and ``timestamp`` attribute which is a Python :class:`~datetime.datetime`
that represents when the event was created. This class is used (inherited)
by both the aggregate :class:`~eventsourcing.domain.Aggregate.Event` class
and the :class:`~eventsourcing.domain.Snapshot` class.

The aggregate :class:`~eventsourcing.domain.Aggregate.Event` class is defined as
a subclass of the domain event base class :class:`~eventsourcing.domain.DomainEvent`.
Aggregate event objects represent original decisions by a domain model
that advance the state of an application.

The aggregate :class:`~eventsourcing.domain.Aggregate.Event` class has a method
:func:`~eventsourcing.domain.Aggregate.Event.mutate` which adjusts the state
of an aggregate. It has an optional argument ``aggregate`` which is used to pass
the aggregate object to which the domain event object pertains into the
method when it is called. It returns an optional ``aggregate`` object, and
the return value can be passed in when calling this method on another event
object. An initial "created" event can construct an aggregate object, a
subsequent event can receive and return an aggregate, and a final "discarded"
event can receive an aggregate and return ``None``. The
:func:`~eventsourcing.domain.Aggregate.Event.mutate` methods of a sequence
of aggregate events can be used to reconstruct a copy of the original aggregate
object. And indeed the :ref:`application repository <Repository>` object has a
:func:`~eventsourcing.application.Repository.get` method which works by
calling these methods.

.. code:: python

    copy = None
    for domain_event in pending_events:
        copy = domain_event.mutate(copy)

    assert isinstance(copy, World)
    assert copy.id == world.id
    assert copy.version == world.version
    assert copy.created_on == world.created_on
    assert copy.modified_on == world.modified_on
    assert copy.history == world.history


The aggregate :class:`~eventsourcing.domain.Aggregate.Event` class has a method
:func:`~eventsourcing.domain.Aggregate.Event.apply`. Like the
:func:`~eventsourcing.domain.Aggregate.Event.mutate` method, it also has
an argument ``aggregate`` which is used to pass the aggregate object
to which the domain event object pertains into the method when it is called.
The :func:`~eventsourcing.domain.Aggregate.Event.mutate` method calls the
event's :func:`~eventsourcing.domain.Aggregate.Event.apply` method before it
returns. The base class :func:`~eventsourcing.domain.Aggregate.Event.apply`
method body is empty, and so this method can be simply overridden (implemented
without a call to the superclass method). It is also not expected to return a value
(any value that it does return will be ignored). Hence this method can be
simply and conveniently implemented in aggregate event classes to apply the
event attribute values to the aggregate.

The ``mutate()`` and ``apply()`` methods of aggregate events effectively implement
the "aggregate projection", which means the function by which the events are processed
to reconstruct the state of the aggregate. An alternative to use ``apply()`` methods
on the event classes is to define apply methods on the aggregate class. A base ``Event``
class can be defined on the aggregate class which simply calls an ``apply()`` method
on the aggregate class. This aggregate ``apply()`` method can be decorated with the
``@singledispatchmethod`` decorator, and then event-specific methods can be defined
and registered that will apply the events to the aggregate. See the ``Cargo`` aggregate
of the :ref:`Cargo Shipping example <Cargo shipping>` for details.

The aggregate :class:`~eventsourcing.domain.Aggregate.Created` class represents
the creation of an aggregate object instance. It is defined as a frozen data class
that extends the base class :class:`~eventsourcing.domain.Aggregate.Event` with
its attribute ``originator_topic`` which is Python :class:`str`. The value of this
attribute will be a :ref:`topic <Topics>` that describes the path to the aggregate
instance's class. It has a :func:`~eventsourcing.domain.Aggregate.Created.mutate`
method which constructs an aggregate object after resolving the ``originator_topic``
value to an aggregate class. It does not call :func:`~eventsourcing.domain.Aggregate.Event.apply`
since the aggregate class ``__init__()`` method receives the "created" event attribute
values and can fully initialise the aggregate object.

Domain event objects are usually created by aggregate methods, as part of a sequence
that determines the state of an aggregate. The attribute values of new event objects are
decided by these methods before the event is created. For example, the aggregate's
:func:`~eventsourcing.domain.Aggregate._create` method uses the given value of its ``id``
argument as the new event's ``originator_id``. It sets the ``originator_version`` to the
value of ``1``. It derives the ``originator_topic`` value from the aggregate class. And
it calls Python's :func:`datetime.now` to create the ``timestamp`` value.

Similarly, the aggregate :func:`~eventsourcing.domain.Aggregate._trigger_event` method uses the
``id`` attribute of the aggregate as the ``originator_id`` of the new domain event. It uses the current
aggregate ``version`` to create the next version number (by adding ``1``) and uses
this value as the ``originator_version`` of the new domain event. It calls
:func:`datetime.now` to create the ``timestamp`` value of the new domain event.

The timestamp values are "timezone aware" datetime objects. The default timezone is
UTC, as defined by Python's :data:`datetime.timezone.utc`. It is recommended to store
date-times as UTC values, and convert to a local timezone in the interface layer according
to the particular timezone of a particular user. However, if necessary, this default can
be changed either by assigning a :class:`datetime.tzinfo` object to the :data:`TZINFO`
attribute of the :mod:`eventsourcing.domain` module. The :data:`eventsourcing.domain.TZINFO`
value can also be configured using environment variables, by setting the environment variable
``TZINFO_TOPIC`` to a string that describes the :ref:`topic <Topics>` of a Python
:data:`datetime.tzinfo` object (for example ``'datetime:timezone.utc'``).


Snapshots
=========

Snapshots speed up aggregate access time, by avoiding the need to retrieve
and apply all the domain events when reconstructing an aggregate object instance.
The library's :class:`~eventsourcing.domain.Snapshot` class can be
used to create and restore snapshots of aggregate object instances.

The :class:`~eventsourcing.domain.Snapshot` class is defined as
a subclass of the domain event base class :class:`~eventsourcing.domain.DomainEvent`.
It is defined as a frozen data class and extends the base class with attributes
``topic`` and ``state``, which hold the topic of an aggregate object class and
the current state of an aggregate object.

.. code:: python

    from eventsourcing.domain import Snapshot

The class method :func:`~eventsourcing.domain.Snapshot.take` can be used to
create a snapshot of an aggregate object. (See the discussion of
:ref:`snapshotting <Snapshotting>` in the application module
documentation for more information about taking snapshots in an
event-sourced application.)

.. code:: python

    snapshot = Snapshot.take(world)

    assert isinstance(snapshot, Snapshot)
    assert snapshot.originator_id == world.id
    assert snapshot.originator_version == world.version
    assert snapshot.topic == "__main__:World", snapshot.topic
    assert snapshot.state["history"] == world.history
    assert snapshot.state["_created_on"] == world.created_on
    assert snapshot.state["_modified_on"] == world.modified_on
    assert len(snapshot.state) == 3


A snapshot's :func:`~eventsourcing.domain.Snapshot.mutate` method can be used to reconstruct its
aggregate object instance.

.. code:: python

    copy = snapshot.mutate(None)

    assert isinstance(copy, World)
    assert copy.id == world.id
    assert copy.version == world.version
    assert copy.created_on == world.created_on
    assert copy.modified_on == world.modified_on
    assert copy.history == world.history

The signature of the :func:`~eventsourcing.domain.Snapshot.mutate` method is the same as the
domain event object method of the same name, so that when reconstructing an aggregate, a list
that starts with a snapshot and continues with the subsequent domain event objects can be
treated in the same way as a list of all the domain event objects of an aggregate.
This similarity is needed by the application :ref:`repository <Repository>`, since
some specialist event stores (e.g. AxonDB) return a snapshot as the first domain event.


.. _Versioning:

Versioning
==========

Versioning allows aggregate and domain event classes to be modified after an application has been deployed.

On both aggregate and domain event classes, the class attribute ``class_version`` can be used to indicate
the version of the class. This attribute is inferred to have a default value of ``1``. If the data model is
changed, by adding or removing or renaming or changing the meaning of values of attributes, subsequent
versions should be given a successively higher number than the previously deployed version. Static methods
of the form ``upcast_vX_vY()`` will be called to update the state of a stored event or snapshot from a lower
version ``X`` to the next higher version ``Y``. Such upcast methods will be called  to upcast the state from
the version of the class with which it was created to the version of the class which will be reconstructed.
For example, upcasting the stored state of an object created at version ``2`` of a class that will be used
to reconstruct an object at version ``4`` of the class will involve calling upcast methods
``upcast_v2_v3()``, and ``upcast_v3_v4()``. If you aren't using snapshots, you don't need to define
upcast methods or version numbers on the aggregate class.

In the example below, version ``1`` of the class ``MyAggregate`` is defined with an attribute ``a``.

.. code:: python

    class MyAggregate(Aggregate):
        def __init__(self, a:str, **kwargs):
            super().__init__(**kwargs)
            self.a = a

        @classmethod
        def create(cls, a:str):
            return cls._create(cls.Created, id=uuid4(), a=a)

        @dataclass(frozen=True)
        class Created(Aggregate.Created):
            a: str


After an application that uses the above aggregate class has been deployed, its ``Created`` events
will have been created and stored with the ``a`` attribute defined. If subsequently the attribute ``b``
is added to the definition of the ``Created`` event, in order for the existing stored events to be
constructed in a way that satisfies the new version of the class, the stored events will need to be
upcast to have a value for ``b``. In the example below, the static method ``upcast_v1_v2()`` defined
on the ``Created`` event sets a default value for ``b`` in the given ``state``. The class attribute
``class_version`` is set to ``2``. The same treatment is given to the aggregate class as the domain
event class, so that snapshots can be upcast.

.. code:: python

    class MyAggregate(Aggregate):
        def __init__(self, a:str, b:int, **kwargs):
            super().__init__(**kwargs)
            self.a = a
            self.b = b

        @classmethod
        def create(cls, a:str, b: int = 0):
            return cls._create(cls.Created, id=uuid4(), a=a, b=b)

        @dataclass(frozen=True)
        class Created(Aggregate.Created):
            a: str
            b: int

            class_version = 2

            @staticmethod
            def upcast_v1_v2(state):
                state["b"] = 0

        class_version = 2

        @staticmethod
        def upcast_v1_v2(state):
            state["b"] = 0


After an application that uses the above version 2 aggregate class has been deployed, its ``Created``
events will have be created and stored with both the ``a`` and ``b`` attributes. If subsequently the
attribute ``c`` is added to the definition of the ``Created`` event, in order for the existing stored
events from version 1 to be constructed in a way that satisfies the new version of the class, they
will need to be upcast to include a value for ``b`` and ``c``. The existing stored events from version 2
will need to be upcast to include a value for ``c``. The additional static method ``upcast_v2_v3()``
defined on the ``Created`` event sets a default value for ``c`` in the given ``state``. The class attribute
``class_version`` is set to ``3``. The same treatment is given to the aggregate class as the domain event
class, so that any snapshots will be upcast.

.. code:: python

    class MyAggregate(Aggregate):
        def __init__(self, a:str, b:int, c:float, **kwargs):
            super().__init__(**kwargs)
            self.a = a
            self.b = b
            self.c = c

        @classmethod
        def create(cls, a:str, b: int = 0, c: float = 0.0):
            return cls._create(cls.Created, id=uuid4(), a=a, b=b, c=c)

        @dataclass(frozen=True)
        class Created(Aggregate.Created):
            a: str
            b: int
            c: float

            class_version = 3

            @staticmethod
            def upcast_v1_v2(state):
                state["b"] = 0

            @staticmethod
            def upcast_v2_v3(state):
                state["c"] = 0.0

        class_version = 3

        @staticmethod
        def upcast_v1_v2(state):
            state["b"] = 0

        @staticmethod
        def upcast_v2_v3(state):
            state["c"] = 0.0


If subsequently a new event is added that manipulates a new attribute that is expected to be initialised
when the aggregate is created, in order that snapshots from earlier version will be upcast, the aggregate
class attribute ``class_version`` will need to be set to ``4`` and a static method ``upcast_v3_v4()``
defined on the aggregate class which upcasts the state of a previously created snapshot. In the example
below, the new attribute ``d`` is initialised in the ``__init__()`` method, and a domain event which
updates ``d`` is defined. Since the ``Created`` event class has not changed, it remains at version ``3``.

.. code:: python

    class MyAggregate(Aggregate):
        def __init__(self, a:str, b:int, c:float, **kwargs):
            super().__init__(**kwargs)
            self.a = a
            self.b = b
            self.c = c
            self.d = False

        @classmethod
        def create(cls, a:str, b: int = 0, c: float = 0.0):
            return cls._create(cls.Created, id=uuid4(), a=a, b=b, c=c)

        @dataclass(frozen=True)
        class Created(Aggregate.Created):
            a: str
            b: int
            c: float

            class_version = 3

            @staticmethod
            def upcast_v1_v2(state):
                state["b"] = 0

            @staticmethod
            def upcast_v2_v3(state):
                state["c"] = 0.0

        def set_d(self, d: bool):
            self._trigger_event(self.DUpdated, d=d)

        @dataclass(frozen=True)
        class DUpdated(Aggregate.Event):
            d: bool

            def apply(self, aggregate: "Aggregate") -> None:
                aggregate.d = self.d

        class_version = 4

        @staticmethod
        def upcast_v1_v2(state):
            state["b"] = 0

        @staticmethod
        def upcast_v2_v3(state):
            state["c"] = 0.0

        @staticmethod
        def upcast_v3_v4(state):
            state["d"] = False


If the value objects used by your events also change, you may also need to define new transcodings
with new names. Simply register the new transcodings after the old, and use a modified ``name`` value
for the transcoding. In this way, the existing encoded values will be decoded by the old transcoding,
and the new instances of the value object class will be encoded with the new version of the transcoding.

In order to support forward compatibility as well as backward compatibility, so that consumers designed for
old versions will not be broken by modifications, it is advisable to restrict changes to existing types to
be additions only, so that existing attributes are unchanged. If existing aspects need to be changed, for
example by renaming or removing an attribute of an event, then it is advisable to define a new type. This
approach depends on consumers overlooking or ignoring new attribute and new types, but they may effectively
be broken anyway by such changes if they no longer see any data.

Including model changes in the domain events may help to inform consumers of changes to the model schema,
and may allow the domain model itself to be validated, so that classes are marked with new versions if
the attributes have changed. This may be addressed by a future version of this library. Considering model
code changes as a sequence of immutable events brings the state of the domain model code itself into the same
form of event-oriented consideration as the consideration of the state an application as a sequence of events.


.. _Namespaced IDs:

Namespaced IDs
==============

Aggregates can be created with `version 5 UUIDs <https://en.wikipedia
.org/wiki/Universally_unique_identifier#Versions_3_and_5_(namespace_name-based)>`_
so that their IDs can be generated from a given name in a namespace. They can
be used for example to create IDs for aggregates with fixed names that you want
to identify by name. For example, you can use this technique to identify a system
configuration object. This technique can also be used to identify index aggregates
that hold the IDs of aggregates with mutable names, or used to index other mutable
attributes of an event sourced aggregate. It isn't possible to change the ID of an
existing aggregate, because the domain events will need to be stored together in a
single sequence. And so, using an index aggregate that has an ID that can be recreated
from a particular value of a mutable attribute of another aggregate to hold the
ID of that aggregate with makes it possible to identify that aggregate from that
particular value. Such index aggregates can be updated when the mutable
attribute changes, or not.

For example, if you have a collection of page aggregates with names that might change,
and you want to be able to identify the pages by name, then you can create index
aggregates with version 5 UUIDs that are generated from the names, and put the IDs
of the page aggregates in the index aggregates. The aggregate classes ``Page`` and ``Index``
in the example code below show how this can be done.

If we imagine we can save these page and index aggregates and retrieve them by ID, we
can imagine retrieving a page aggregate using its name by firstly recreating an index ID
from the page name, retrieving the index aggregate using that ID, getting the page ID
from the index aggregate, and then using that ID to retrieve the page aggregate. When
the name is changed, a new index aggregate can be saved along with the page, so that
later the page aggregate can be retrieved using the new name. See the discussion about
:ref:`saving multiple aggregates <Saving multiple aggregates>` to see an example of
how this can work.

.. code:: python

    from dataclasses import dataclass
    from uuid import NAMESPACE_URL, uuid5, UUID

    from eventsourcing.domain import Aggregate


    class Page(Aggregate):
        def __init__(self, name: str, body: str, **kwargs):
            super(Page, self).__init__(**kwargs)
            self.name = name
            self.body = body

        @classmethod
        def create(cls, name: str, body: str = ""):
            return cls._create(
                id=uuid4(),
                event_class=cls.Created,
                name=name,
                body=body
            )

        @dataclass(frozen=True)
        class Created(Aggregate.Created):
            name: str
            body: str

        def update_name(self, name: str):
            self._trigger_event(self.NameUpdated, name=name)

        @dataclass(frozen=True)
        class NameUpdated(Aggregate.Event):
            name: str

            def apply(self, page: "Page"):
                page.name = self.name


    class Index(Aggregate):
        def __init__(self, ref, **kwargs):
            super().__init__(**kwargs)
            self.ref = ref

        @classmethod
        def create_id(cls, name: str):
            return uuid5(NAMESPACE_URL, f"/pages/{name}")

        @classmethod
        def create(cls, page: Page):
            return cls._create(
                event_class=cls.Created,
                id=cls.create_id(page.name),
                ref=page.id
            )

        @dataclass(frozen=True)
        class Created(Aggregate.Created):
            ref: UUID

        def update_ref(self, ref):
            self._trigger_event(self.RefUpdated, ref=ref)

        @dataclass(frozen=True)
        class RefUpdated(Aggregate.Event):
            ref: UUID

            def apply(self, index: "Index"):
                index.ref = self.ref


We can use the classes above to create a "page" aggregate with a name that
we will then change. We can at the same time create an index object for the
page.

.. code:: python

    page = Page.create(name="Erth")
    index1 = Index.create(page)


Let's imagine these two aggregate are saved together, and having
been saved can be retrieved by ID. See the discussion about
:ref:`saving multiple aggregates <Saving multiple aggregates>`
to see how this works in an application object.

We can use the page name to recreate the index ID, and use the index
ID to retrieve the index aggregate. We can then obtain the page ID from
the index aggregate, and then use the page ID to get the page aggregate.

.. code:: python

    index_id = Index.create_id("Erth")
    assert index_id == index1.id
    assert index1.ref == page.id


Now let's imagine we want to correct the name of the page. We
can update the name of the page, and create another index aggregate
for the new name, so that later we can retrieve the page using
its new name.

.. code:: python

    page.update_name("Earth")
    index2 = Index.create(page)


We can now use the new name to get the ID of the second index aggregate,
and imagine using the second index aggregate to get the ID of the page.

.. code:: python

    index_id = Index.create_id("Earth")
    assert index_id == index2.id
    assert index2.ref == page.id

Saving and retrieving aggregates by ID is demonstrated in the discussion
about :ref:`saving multiple aggregates <Saving multiple aggregates>` in
the :ref:`applications <Application objects>` documentation.

.. _Topics:

Topics
======

A "topic" in this library is a string formed from joining with a colon character
(``':'``) the path to a Python module (e.g. ``'eventsourcing.domain'``) with the qualified
name of an object in that module (e.g. ``'Aggregate.Created'``). For example
``'eventsourcing.domain:Aggregate.Created'`` describes the path to the library's
:class:`~eventsourcing.domain.Aggregate.Created` class. The library's
:mod:`~eventsourcing.utils` module contains the functions :func:`~eventsourcing.utils.resolve_topic()`
and :func:`~eventsourcing.utils.get_topic()` which are used in the library to resolve
a given topic to a Python object, and to construct a topic for a given Python object.


Classes
=======

.. automodule:: eventsourcing.domain
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__

.. automodule:: eventsourcing.utils
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__
