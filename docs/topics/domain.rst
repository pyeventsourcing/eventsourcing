==============================================
:mod:`~eventsourcing.domain` --- Domain models
==============================================


This module supports the development of event-sourced domain models.

Following the terminology of *Domain-Driven Design*, an event-sourced domain
model has many event-sourced **aggregates**. The state of an event-sourced
aggregate is determined by a sequence of immutable **domain events**. The
time needed to reconstruct an aggregate from its domain events can be reduced
by using **snapshots**.

The classes in this module were first introduced merely as a way of showing
how the persistence module can be used. The persistence module is the original
core of this library, and is the cohesive mechanism for storing and retrieving
sequences ("streams") of immutable events. But without showing how this mechanism
can be used to develop a domain model, there is a gap where application developers
would instead expect some solid ground on which to build a "domain object" model
for their applications. Through a process of refinement over several years, the
domain model classes in this module have become useful as base classes for a
stand-alone event-sourced domain model. It's certainly possible to do without
these classes, and alternative ways of coding domain models are encouraged. However,
if you want to make progress efficiently, you may find that using the ``Aggregate``
base class and the ``@event`` decorator will speed your creativity in developing a
most compact and effective event-sourced domain model.

This module appears first in the documentation, not because it is the most
important section, but rather because this was overwhelmingly the order
preferred by the community of users of the library, as expressed in a vote
on the matter in 2021.


.. _Events:

Domain events
=============

Domain event objects are created but do not change.
The library's :class:`~eventsourcing.domain.DomainEvent` class is a base
class for domain events. It is defined as a `frozen Python data class
<https://docs.python.org/3/library/dataclasses.html#frozen-instances>`_
to model the immutable character of a domain event. It has an ``originator_id``
attribute which is a Python :class:`~uuid.UUID` that identifies a sequence
(or "stream") to which an event belongs, an ``originator_version``
attribute which is a Python :class:`int` that determines its position
in that sequence, and a ``timestamp`` attribute which is a Python
:class:`~datetime.datetime` that represents when the event occurred.

.. code:: python

    from datetime import datetime
    from uuid import uuid4

    from eventsourcing.domain import DomainEvent


    originator_id = uuid4()

    domain_event = DomainEvent(
        originator_id=originator_id,
        originator_version=2,
        timestamp=datetime(2022, 2, 2),
    )
    assert domain_event.originator_id == originator_id
    assert domain_event.originator_version == 2
    assert domain_event.timestamp == datetime(2022, 2, 2)


Domain event objects are ordered in their sequence by their version numbers,
and not by their timestamps. The timestamps have no consequences for the operation
of this library, and are included to give an approximate indication of when a
domain event object created. The reason for ordering a sequence of events with
integers and not timestamps is that integers can form a gapless sequence that
excludes the possibility for inserting new items before old ones, and timestamps
can suffer from clock skews.

The library's :class:`~eventsourcing.domain.AggregateEvent` base class is defined as
a subclass of :class:`~eventsourcing.domain.DomainEvent`. It can be used to
define concrete aggregate event objects in your domain model.
Aggregate event objects represent original decisions by a domain model that advance
the state of an application.

.. code:: python

    from eventsourcing.domain import AggregateEvent


    aggregate_event = AggregateEvent(
        originator_id=originator_id,
        originator_version=2,
        timestamp=datetime(2022, 2, 2),
    )
    assert aggregate_event.originator_id == originator_id
    assert aggregate_event.originator_version == 2
    assert aggregate_event.timestamp == datetime(2022, 2, 2)

Aggregate events are uniquely identifiable in a domain
model by the combination of their ``originator_id`` and ``originator version``.

The :class:`~eventsourcing.domain.AggregateEvent` class has a
:func:`~eventsourcing.domain.AggregateEvent.mutate` method which adjusts the state
of an object passed in using the ``aggregate`` argument. This method checks the
event's ``originator_version`` equals the current aggregate
version number plus ``1``. It then increments the aggregate's
:py:obj:`~eventsourcing.domain.Aggregate.version` attribute.
It assigns the event's ``timestamp`` to the aggregate's
:py:obj:`~eventsourcing.domain.Aggregate.modified_on` attribute.
It returns the modified object.

.. code:: python

    class A:
        def __init__(self, id, version):
            self.id = id
            self.version = version


    a = A(id=originator_id, version=1)
    a = aggregate_event.mutate(a)
    assert a.version == 2
    assert a.modified_on == datetime(2022, 2, 2)


The :class:`~eventsourcing.domain.AggregateEvent` class also has an
:func:`~eventsourcing.domain.AggregateEvent.apply` method, which is called
by the :func:`~eventsourcing.domain.AggregateEvent.mutate` method. The
:func:`~eventsourcing.domain.AggregateEvent.apply` method has
a non-optional argument ``aggregate`` which is used to provide the aggregate
object to which the domain event object pertains. The base class's
:func:`~eventsourcing.domain.AggregateEvent.apply` method body is empty, and
so this method can be simply overridden (implemented without a call to the
superclass method). It is also not expected to return a value (any value that
it does return will be ignored). Hence this method can be simply and conveniently
implemented in aggregate event classes to apply an event's attribute values to an
aggregate. The :func:`~eventsourcing.domain.AggregateEvent.apply` method is called
after the validation checks and before modifying the aggregate's state, so that if
it raises an exception, then the aggregate will remain unmodified by the
:func:`~eventsourcing.domain.AggregateEvent.mutate` method.

.. code:: python

    class MyEvent(AggregateEvent):
        full_name: str

        def apply(self, aggregate):
            aggregate.full_name = self.full_name


    my_event = MyEvent(
        originator_id=originator_id,
        originator_version=3,
        timestamp=datetime(2033, 3, 3),
        full_name="Eric Idle"
    )


    a = my_event.mutate(a)
    assert a.version == 3
    assert a.modified_on == datetime(2033, 3, 3)
    assert a.full_name == "Eric Idle"


The library also has an
:class:`~eventsourcing.domain.AggregateCreated` class which represents
the creation of an aggregate. It extends :class:`~eventsourcing.domain.AggregateEvent` with
its attribute ``originator_topic`` which is a Python :class:`str`. The value of this
attribute will be a :ref:`topic <Topics>` that describes the path to the aggregate
instance's class. It has a :func:`~eventsourcing.domain.AggregateCreated.mutate`
method which constructs an aggregate object after resolving the ``originator_topic``
value to an aggregate class. Although this method has the same signature as the base class's
method, the argument is expected to be ``None`` and is anyway ignored. It does not call
:func:`~eventsourcing.domain.AggregateEvent.apply` since the aggregate class's ``__init__()``
method receives the "created" event attribute values and can fully initialise the aggregate
object in the usual way.

.. code:: python

    from eventsourcing.domain import AggregateCreated


    aggregate_created = AggregateCreated(
        originator_topic="eventsourcing.domain:Aggregate",
        originator_id=originator_id,
        originator_version=1,
        timestamp=datetime(2011, 1, 1),
    )

    a = aggregate_created.mutate(None)
    assert a.__class__.__name__ == "Aggregate"
    assert a.__class__.__module__ == "eventsourcing.domain"
    assert a.id == originator_id
    assert a.version == 1
    assert a.modified_on == datetime(2011, 1, 1)


The object returned by the :func:`~eventsourcing.domain.AggregateEvent.mutate` method can
be passed in when calling the method on another event object. Hence, the
:func:`~eventsourcing.domain.AggregateEvent.mutate` methods of a sequence of
aggregate events can be used successively to reconstruct the current state of
an aggregate.

.. code:: python

    a = aggregate_created.mutate(None)
    assert a.id == originator_id
    assert a.version == 1
    assert a.modified_on == datetime(2011, 1, 1)

    a = aggregate_event.mutate(a)
    assert a.id == originator_id
    assert a.version == 2
    assert a.modified_on == datetime(2022, 2, 2)

    a = my_event.mutate(a)
    assert a.id == originator_id
    assert a.version == 3
    assert a.modified_on == datetime(2033, 3, 3)
    assert a.full_name == "Eric Idle"


The :func:`~eventsourcing.domain.AggregateEvent.mutate` and
:func:`~eventsourcing.domain.AggregateEvent.apply` methods of aggregate events
can be used effectively to implement a "mutator function", or "aggregate projection",
by which the state of an aggregate is reconstructed from its history of events.
This is essentially how the :func:`~eventsourcing.application.Repository.get`
method of an :ref:`application repository <Repository>` reconstructs an aggregate
from stored events when the aggregate is requested by ID.

.. code:: python

    def reconstruct_aggregate_from_events(events):
        a = None
        for event in events:
            a = event.mutate(a)
        return a


    events = [
        aggregate_created,
        aggregate_event,
        my_event,
    ]

    a = reconstruct_aggregate_from_events(events)
    assert a.id == originator_id
    assert a.version == 3
    assert a.modified_on == datetime(2033, 3, 3)
    assert a.full_name == "Eric Idle"


By making the ``aggregate`` argument and return value optional,
"created" events can be defined which start from ``None`` and "discarded" events
can be defined which return ``None``. For example, an initial "created" event can
construct an aggregate object, subsequent events can receive an aggregate and
return a modified aggregate, and a final "discarded" event can receive an aggregate
and return ``None``.

.. code:: python

    class AggregateDiscarded(AggregateEvent):
        def mutate(self, aggregate):
            super().mutate(aggregate)
            aggregate._is_discarded = True
            return None


    aggregate_discarded = AggregateDiscarded(
        originator_id=originator_id,
        originator_version=4,
        timestamp=datetime(2044, 4, 4),
    )


    events.append(aggregate_discarded)
    a = reconstruct_aggregate_from_events(events)
    assert a is None


An alternative to using :func:`~eventsourcing.domain.AggregateEvent.apply` methods
on the event classes is to define apply methods on the aggregate class. A base ``Event``
class can be defined on the aggregate class with an ``apply()`` method which simply
calls an ``apply()`` method on the aggregate class that has the event as an argument.
The aggregate's ``apply()`` method can be decorated with the
``@singledispatchmethod`` decorator, or implemented as a big if-else block, and then
event-specific parts of the projection can be defined that will apply particular types
events to the aggregate in a particular way. See the ``Cargo`` aggregate in the domain
model section of the :ref:`Cargo Shipping example <Cargo shipping>` for an example of
this alternative. This has the advantage of setting values on ``self``, which avoids
the reverse of intuition that occurs when writing ``apply()`` methods on the events,
and makes it legitimate to set values on "private" attributes. However, there is
quite a lot of "boiler plate" that results from coding this on every aggregate class.

A further alternative is to use a function at the module level which has both the event
and the aggregate as arguments, but then the projection becomes even more distant from
definition of the event. It's also possible to rework the mutate methods in these ways,
but then the common behaviours will need to repeated for each part of the projection
that handles a particular type of event, and for all the types of event, which is
repetitive and so isn't recommended. And also the issue of setting "private" attributes
on the aggregate returns.

A further alternative, which is highly recommended, is to use the new
:ref:`declarative syntax <Declarative syntax>`, especially the ``@event``
decorator, which is used on the project's README page, and which is explained
in detail below.

This library's :class:`~eventsourcing.domain.Snapshot` class is also defined as a
subclass of the :class:`~eventsourcing.domain.DomainEvent` class, and works in a
similar way to the aggregate event classes mentioned above. See the :ref:`Snapshots
<Snapshots>` section for more information about snapshots.


Aggregates in DDD
=================

Aggregates are enduring objects which enjoy adventures of change. The
book *Domain-Driven Design* by Eric Evans describes a design pattern
called 'aggregate' in the following way.

.. pull-quote::

    *"An aggregate is a cluster of associated objects that we treat as a unit
    for the purpose of data changes. Each aggregate has a root and a boundary...
    Therefore... Cluster the entities and value objects into aggregates and
    define boundaries around each. Choose one entity to be the root of each
    aggregate, and control all access to the objects inside the boundary
    through the root. Allow external objects to hold references to the
    root only."*

An aggregate is a cluster of 'entities' and 'value objects'. An entity is an
object with a fixed unique identity and other attributes that may vary. A
value object does not vary, and does not necessarily have a unique identity.
This basic notion of a cluster of software objects is understandable as
straightforward `object-oriented programming
<https://en.wikipedia.org/wiki/Object-oriented_programming>`_.

An aggregate has a 'root'. The root of an aggregate is an entity.
This entity is known as the 'root entity' or the 'aggregate root'. Entities
have IDs and the ID of the root entity is used to uniquely identify the
cluster of objects in a domain model. Access to the cluster of objects
is made through the root entity.

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
cluster of objects will always follow from decisions made by the aggregate.
It will always be true that a decision itself, having happened, does not change.
But the results of such a decision are not always expressed explicitly as an
immutable event object. Event-sourced aggregates make these things explicit.

.. pull-quote::

    *"Explicit is better than implicit."*


To make things explicit, a decision made in the command method of an
aggregate can be coded and recorded as an immutable 'domain event'
object, and this object can be used to evolve the aggregate's cluster of
entities and value objects.
For each event-sourced aggregate, there will a sequence of domain event objects,
and the state of an event-sourced aggregate will be determined by its sequence of
domain event objects. The state of an aggregate can change, and its sequence
of domain events can be augmented. But once created the individual domain
event objects do not change. They are what they are.

The state of an aggregate, event-sourced or not, is changed by calling its
command methods. In an event-sourced aggregate, the command methods create
new domain event objects. The domain events are used to evolve the state of
the aggregate. The domain events can be recorded and used to reconstruct
the state of the aggregate in the future and elsewhere.

One command may result in many new domain event objects, and a single client request may
result in the execution of many commands. To maintain consistency in the domain model,
all the domain events triggered by responding to a single client request must be recorded
atomically in the order they were created, otherwise the recorded state of the aggregate
may become inconsistent with respect to that which was desired or expected.

Aggregate base class
--------------------

This library's :class:`~eventsourcing.domain.Aggregate` class is a base class for
event-sourced aggregates. It can be used to develop event-sourced aggregates. See
for example the ``World`` aggregate in the :ref:`Simple example <Aggregate simple example>`
below.


.. code:: python

    from eventsourcing.domain import Aggregate


It had three methods which can be used by and on subclasses:

* the "private" class method :func:`~eventsourcing.domain.MetaAggregate._create`
  will create new aggregate objects;

* the object method :func:`~eventsourcing.domain.Aggregate.trigger_event`
  can be used to trigger subsequent events; and

* the object method :func:`~eventsourcing.domain.Aggregate.collect_events`
  returns new events that have just been triggered.

These methods are explained below.


Creating new aggregates
-----------------------

Firstly, the :class:`~eventsourcing.domain.Aggregate` class has a "private" class
method :func:`~eventsourcing.domain.MetaAggregate._create` which can be used to create
a new aggregate object.

.. code:: python

    aggregate_id = uuid4()
    aggregate = Aggregate._create(Aggregate.Created, id=aggregate_id)


When called, this method creates the first of a new sequence of aggregate event
objects, and uses this aggregate event object to construct and initialise an
instance of the aggregate class, which it then returns to the caller.

Usually, this generically named "private" method will be called by a "public"
class method defined on a subclass of the :class:`~eventsourcing.domain.Aggregate`
base class. For example, see the class method ``create()`` of ``World`` aggregate
class in the :ref:`Simple example <Aggregate simple example>` below. Your public
"create" method should be named after a particular concern
in your domain. Nevertheless, we need a name to refer to this sort of thing
in general, and the words "create" and "created" are used for that purpose.

The :func:`~eventsourcing.domain.MetaAggregate._create` method has a required positional
argument ``event_class`` which is used by the caller to pass a domain event class that
will represent the fact that an aggregate was "created". A domain event object of this
type will be constructed by this method, and this domain event object will be used to
construct and initialise an aggregate object.

The :class:`~eventsourcing.domain.Aggregate` class is defined with
a nested class :class:`~eventsourcing.domain.Aggregate.Created`, which is
is a subclass of the :class:`~eventsourcing.domain.AggregateCreated` base class
discussed in the :ref:`Domain events <Events>` section above. It can be used
or extended (and is used in the example above) to represent the fact that an aggregate
was "created".  It is defined for convenience, and adds no further attributes or methods.

The :class:`~eventsourcing.domain.Aggregate.Created` class can
be used directly, but can also be subclassed to define a particular "created"
event class for a particular aggregate class, with a suitable name and
with suitable extra attributes that represent the particular beginning
of a particular type of aggregate. Aggregate event classes should be named using
past participles (regular or irregular). And a "created" event class should be named
using a past participle that describes the initiation or the beginning of something,
such as "Started", "Opened", or indeed "Created".

The :func:`~eventsourcing.domain.MetaAggregate._create` method also has
an optional ``id`` argument which should be a Python :class:`~uuid.UUID`
object that will be used to uniquely identify the aggregate in the domain
model. It uses the given value of its ``id`` argument as the new event's
``originator_id``. If a value is not provided, by default a
`version 4 UUID <https://en.wikipedia.org/wiki/Universally_unique_identifier#Version_4_(random)>`_
will be created by calling its :func:`~eventsourcing.domain.MetaAggregate.create_id`
method. It will also, by default, set the ``originator_version``
to the value of ``1``. It derives the event's ``originator_topic`` value from the
aggregate class itself, using the library's :func:`~eventsourcing.utils.get_topic`
function. And it calls :func:`datetime.now` to create the event's ``timestamp``
value, a timezone-aware Python :class:`~datetime.datetime` object.

The :func:`~eventsourcing.domain.MetaAggregate._create` method also accepts variable
keyword arguments, ``**kwargs``, which if given will also be used to construct the event
object in addition to those mentioned above. Since the "created" event object will be
constructed with these additional arguments, so these other method arguments must be
matched by the attributes of your "created" event class. The concrete aggregate class's
initializer method :func:`__init__` should also be coded to accept these extra arguments.

After creating the event object, the :func:`~eventsourcing.domain.Aggregate._create` method
will construct the aggregate object by calling the event object's
:func:`~eventsourcing.domain.AggregateEvent.mutate` method. It will then return the aggregate
object to the caller.

Having been created, an aggregate object will have an aggregate ID. The ID is presented
by its :py:obj:`~eventsourcing.domain.Aggregate.id` property. The ID will be identical to
the value passed to the :func:`~eventsourcing.domain.MetaAggregate._create` method
with the ``id`` argument.

.. code:: python

    assert aggregate.id == aggregate_id


A new aggregate instance has a version number. The version number is presented by its
:py:obj:`~eventsourcing.domain.Aggregate.version` property, and is a Python :class:`int`.
The initial version of a newly created aggregate is, by default, always ``1``. If you want
to start at a different number, set ``INITIAL_VERSION`` on the aggregate class.

.. code:: python

    assert aggregate.version == 1


A new aggregate instance has a :py:obj:`~eventsourcing.domain.Aggregate.created_on`
property which gives the date and time when an aggregate object was created, and is determined
by the timestamp attribute of the first event in the aggregate's sequence, which is the "created"
event. The timestamps are timezone-aware Python :class:`~datetime.datetime` objects.

.. code:: python

    assert isinstance(aggregate.created_on, datetime)


A new aggregate instance also has a :py:obj:`~eventsourcing.domain.Aggregate.modified_on`
property which gives the date and time when an aggregate object was last modified, and is determined
by the timestamp attribute of the last event in the aggregate's sequence.

.. code:: python

    assert isinstance(aggregate.modified_on, datetime)


Initially, since there is only one event in the aggregate's sequence,
the :py:obj:`~eventsourcing.domain.Aggregate.created_on` and
:py:obj:`~eventsourcing.domain.Aggregate.modified_on` values are
identical, and equal to the timestamp of the "created" event.

.. code:: python

    assert aggregate.created_on == aggregate.modified_on


Triggering subsequent events
----------------------------

Secondly, the :class:`~eventsourcing.domain.Aggregate` class has a
method :func:`~eventsourcing.domain.Aggregate.trigger_event` which can be called
to trigger a subsequent aggregate event object.

.. code:: python

    aggregate.trigger_event(Aggregate.Event)


This method can be called by the command methods of an aggregate to
capture the decisions that are made. For example, see the
``make_it_so()`` method of the ``World`` class in the :ref:`Simple example <Aggregate simple example>`
below. The creation of the aggregate event object is the final stage in the
coming-to-be of a private individual occasion of experience within the aggregate,
that begins before the event object is created. The event object is the beginning
of a transition of this private individuality to the publicity of many such things,
one stubborn fact amongst the many which together determine the current state of an
event-sourced application.

Like the :func:`~eventsourcing.domain.MetaAggregate._create` method, the
:func:`~eventsourcing.domain.Aggregate.trigger_event` method has a required
positional argument ``event_class``, which is the type of aggregate
event object to be triggered.

It uses the ``id`` attribute of the aggregate as the ``originator_id`` of the new
domain event. It uses the current aggregate ``version`` to create the next version
number (by adding ``1``) and uses this value as the ``originator_version`` of the
new aggregate event. It calls :func:`datetime.now` to create the ``timestamp``
value of the new domain event, a timezone-aware Python :class:`~datetime.datetime` object

The :class:`~eventsourcing.domain.Aggregate` class has a nested
:class:`~eventsourcing.domain.Aggregate.Event` class. It is defined
as a subclass of the :class:`~eventsourcing.domain.AggregateEvent`
discussed above in the section on :ref:`Domain events <Events>`.
The :class:`~eventsourcing.domain.Aggregate.Event` class can be
used as a base class to define the particular aggregate event classes
needed by in your domain model. For example, see the ``SomethingHappened``
class in the :ref:`Simple example <Aggregate simple example>` below.
Aggregate event classes are usually named using past participles
to describe what was decided by the command method, such as "Done",
"Updated", "Closed"... names that are meaningful in your domain,
expressing and helping to constitute your project's ubiquitous language.

The :func:`~eventsourcing.domain.Aggregate.trigger_event` method also accepts arbitrary
keyword-only arguments, which will be used to construct the aggregate event object. As with the
:func:`~eventsourcing.domain.MetaAggregate._create` method described above, the event object will be constructed
with these arguments, and so any extra arguments must be matched by the expected values of
the event class. For example, ``what`` on the ``SomethingHappened`` event class definition
in the :ref:`Simple example <Aggregate simple example>` below matches the ``what=what``
keyword argument passed in the call to the :func:`~eventsourcing.domain.Aggregate.trigger_event`
method in the ``make_it_so()`` command.

After creating the aggregate event object, the :func:`~eventsourcing.domain.Aggregate.trigger_event` method
will apply the event to the aggregate by calling the event object's
:func:`~eventsourcing.domain.AggregateEvent.mutate` method, which will
call the event's :func:`~eventsourcing.domain.AggregateEvent.apply` method,
and then update the ``version`` and ``modified_on`` attributes.

Hence, after calling :func:`~eventsourcing.domain.Aggregate.trigger_event`, the aggregate's
:py:obj:`~eventsourcing.domain.Aggregate.version` will have been incremented by ``1``, and the
``modified_on`` time should be greater than the ``created_on`` time.

.. code:: python

    assert aggregate.version == 2
    assert aggregate.modified_on > aggregate.created_on


Collecting pending events
-------------------------

Thirdly, the :class:`~eventsourcing.domain.Aggregate` class has a "public" object method
:func:`~eventsourcing.domain.Aggregate.collect_events`
which can be called to collect the aggregate events that have been created
either after the last call to this method, or after the aggregate object was
constructed if the method hasn't been called.

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


The :func:`~eventsourcing.domain.Aggregate.collect_events` method is called without
any arguments. In the example above, we can see two aggregate event objects have been
collected, because we created an aggregate and then triggered a subsequent event.


.. _Aggregate simple example:

Simple example
==============

In the example below, the ``World`` aggregate is defined as a subclass of the :class:`~eventsourcing.domain.Aggregate` class.

.. code:: python

    class World(Aggregate):
        def __init__(self):
            self.history = []

        @classmethod
        def create(cls):
            return cls._create(cls.Created, id=uuid4())

        def make_it_so(self, what):
            self.trigger_event(self.SomethingHappened, what=what)

        class SomethingHappened(Aggregate.Event):
            what: str

            def apply(self, world):
                world.history.append(self.what)


The ``__init__()`` method
initialises a ``history`` attribute with an empty Python ``list`` object.

The ``World.create()`` class method creates and returns
a new ``World`` aggregate object. It calls the base class's
:func:`~eventsourcing.domain.MetaAggregate._create` method that
we discussed above. It uses its own ``Created`` event class as
the value of the ``event_class`` argument. As above, it uses a
`version 4 UUID <https://en.wikipedia.org/wiki/Universally_unique_identifier#Version_4_(random)>`_
object as the value of the ``id`` argument. See the :ref:`Namespaced IDs <Namespaced IDs>`
section below for a discussion about using version 5 UUIDs.

The ``make_it_so()`` method is a command method that triggers
a ``World.SomethingHappened`` domain event. It calls the base class
:func:`~eventsourcing.domain.Aggregate.trigger_event` method.
The event is triggered with the method argument ``what``.

The nested ``SomethingHappened`` class is a frozen data class that extends the
base aggregate event class ``Aggregate.Event`` (also a frozen data class) with a
field ``what`` which is defined as a Python :class:`str`. An ``apply()`` method
is defined which appends the ``what`` value to the aggregate's ``history``. This
method is called when the event is triggered (see :ref:`Domain events <Events>`).

By defining the event class under the command method which triggers it, and then
defining an ``apply()`` method as part of the event class definition, the story of
calling a command method, triggering an event, and evolving the state of the aggregate
is expressed in three cohesive parts that are neatly co-located.

Having defined the ``World`` aggregate class, we can create a new ``World``
aggregate object by calling the ``World.create()`` class method.

.. code:: python

    world = World.create()
    assert isinstance(world, World)

The aggregate's attributes ``created_on`` and ``modified_on`` show
when the aggregate was created and when it was modified. Since there
has only been one domain event, these are initially equal.
These values follow from the ``timestamp`` values of the domain event
objects, and represent when the aggregate's first and last domain events
were created.

.. code:: python

    assert world.created_on == world.modified_on


We can now call the aggregate object methods. The ``World`` aggregate has a command
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
a list of pending events. The pending events can be collected by calling
the aggregate's :func:`~eventsourcing.domain.Aggregate.collect_events` method.
These events are pending to be saved, and indeed the library's
:ref:`application <Application objects>` object has a
:func:`~eventsourcing.application.Application.save` method which
works by calling this method. So far, we have created four domain events and
we have not yet collected them, and so there will be four pending events: one
``Created`` event, and three ``SomethingHappened`` events.

.. code:: python

    # Has four pending events.
    assert len(world.pending_events) == 4

    # Collect pending events.
    pending_events = world.collect_events()
    assert len(pending_events) == 4
    assert len(world.pending_events) == 0

    assert isinstance(pending_events[0], World.Created)
    assert isinstance(pending_events[1], World.SomethingHappened)
    assert isinstance(pending_events[2], World.SomethingHappened)
    assert isinstance(pending_events[3], World.SomethingHappened)
    assert pending_events[1].what == "dinosaurs"
    assert pending_events[2].what == "trucks"
    assert pending_events[3].what == "internet"

    assert pending_events[0].timestamp == world.created_on
    assert pending_events[3].timestamp == world.modified_on


As discussed above, the event objects can be used to reconstruct
the current state of the aggregate, by calling their
:func:`~eventsourcing.domain.AggregateEvent.mutate` methods.

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


The :func:`~eventsourcing.application.Repository.get`
method of the :ref:`application repository <Repository>` class
works by calling these methods in this way for this purpose.


.. _Snapshots:

Snapshots
=========

Snapshots speed up aggregate access time, by avoiding the need to retrieve
and apply all the domain events when reconstructing an aggregate object instance.
The library's :class:`~eventsourcing.domain.Snapshot` class can be used to create
and restore snapshots of aggregate object instances. See :ref:`Snapshotting <Snapshotting>`
in the application module documentation for more information about taking snapshots
in an event-sourced application.

The :class:`~eventsourcing.domain.Snapshot` class is defined as
a subclass of the domain event base class :class:`~eventsourcing.domain.DomainEvent`.
It is defined as a frozen data class and extends the base class with attributes
``topic`` and ``state``, which hold the topic of an aggregate object class and
the current state of an aggregate object.

.. code:: python

    from eventsourcing.domain import Snapshot

The class method :func:`~eventsourcing.domain.Snapshot.take` can be used to
create a snapshot of an aggregate object.

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
        def __init__(self, a:str):
            self.a = a

        @classmethod
        def create(cls, a:str):
            return cls._create(cls.Created, id=uuid4(), a=a)

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
        def __init__(self, a:str, b:int):
            self.a = a
            self.b = b

        @classmethod
        def create(cls, a:str, b: int = 0):
            return cls._create(cls.Created, id=uuid4(), a=a, b=b)

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
        def __init__(self, a:str, b:int, c:float):
            self.a = a
            self.b = b
            self.c = c

        @classmethod
        def create(cls, a:str, b: int = 0, c: float = 0.0):
            return cls._create(cls.Created, id=uuid4(), a=a, b=b, c=c)

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
        def __init__(self, a:str, b:int, c:float):
            self.a = a
            self.b = b
            self.c = c
            self.d = False

        @classmethod
        def create(cls, a:str, b: int = 0, c: float = 0.0):
            return cls._create(cls.Created, id=uuid4(), a=a, b=b, c=c)

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
            self.trigger_event(self.DUpdated, d=d)

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

    from uuid import NAMESPACE_URL, uuid5, UUID
    from typing import Optional

    from eventsourcing.domain import Aggregate


    class Page(Aggregate):
        def __init__(self, name: str, body: str):
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

        class Created(Aggregate.Created):
            name: str
            body: str

        def update_name(self, name: str):
            self.trigger_event(self.NameUpdated, name=name)

        class NameUpdated(Aggregate.Event):
            name: str

            def apply(self, page: "Page"):
                page.name = self.name


    class Index(Aggregate):
        def __init__(self, name: str, ref: UUID):
            self.name = name
            self.ref = ref

        @classmethod
        def create(cls, name: str, ref: UUID):
            return cls._create(
                event_class=cls.Created,
                id=cls.create_id(page.name),
                name=page.name,
                ref=page.id
            )

        @staticmethod
        def create_id(name: str):
            return uuid5(NAMESPACE_URL, f"/pages/{name}")

        class Created(Aggregate.Created):
            name: str
            ref: UUID

        def update_ref(self, ref):
            self.trigger_event(self.RefUpdated, ref=ref)

        class RefUpdated(Aggregate.Event):
            ref: Optional[UUID]

            def apply(self, index: "Index"):
                index.ref = self.ref


We can use the classes above to create a "page" aggregate with a name that
we will then change. We can at the same time create an index object for the
page.

.. code:: python

    page = Page.create(name="Erth")
    index1 = Index.create(page.name, page.id)


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
    index2 = Index.create(page.name, page.id)

We can drop the reference from the old index, so that it can
be used to refer to a different page.

.. code: python

    index.1.update_ref(None)

We can now use the new name to get the ID of the second index aggregate,
and imagine using the second index aggregate to get the ID of the page.

.. code:: python

    index_id = Index.create_id("Earth")
    assert index_id == index2.id
    assert index2.ref == page.id


Saving and retrieving aggregates by ID is demonstrated in the discussion
about :ref:`saving multiple aggregates <Saving multiple aggregates>` in
the :ref:`applications <Application objects>` documentation.

.. _Declarative syntax:

Declarative syntax
==================

You may have noticed a certain amount of repetition in the definitions of the
aggregates above. In several places, the same argument was defined in a command
method, on an event class, and in an apply method. The library offers a more concise
way to express aggregates by using a declarative syntax. This is probably the most
concise way of expressing an event-sourced domain model across all programming
languages.


Create new aggregate by calling the aggregate class directly
------------------------------------------------------------

A new event sourced aggregate can be created by calling the aggregate class
directly. You don't actually need to define a class method to do this, although
you may wish to express your project's ubiquitous language by doing so.

Calling the aggregate class directly will firstly create a created event (an instance
of the aggregate's created event class) and use that event object to construct an
instance of the aggregate class.

.. code:: python

    class MyAggregate(Aggregate):
        class Created(Aggregate.Created):
            pass


    # Call the class directly.
    agg = MyAggregate()

    # There is one pending event.
    pending_events = agg.collect_events()
    assert len(pending_events) == 1
    assert isinstance(pending_events[0], MyAggregate.Created)

    # The pending event can be used to reconstruct the aggregate.
    copy = pending_events[0].mutate(None)
    assert copy.id == agg.id
    assert copy.created_on == agg.created_on


Using the init method to define the created event class
-------------------------------------------------------

If a created event class is not defined on an aggregate class,
one will be automatically defined. The attributes of this event
class will be derived by inspecting the signature of the ``__init__()`` method.
The example below has an init method that has a ``name`` argument.
Because this example doesn't have a created event class defined
explicitly on the aggregate class, a created event class will be
defined automatically to match the signature of the init method.
That is, a created event class will be defined that has an attribute
``name``.

.. code:: python

    class MyAggregate(Aggregate):
        def __init__(self, name):
            self.name = name


    # Call the class with a 'name' argument.
    agg = MyAggregate(name="foo")
    assert agg.name == "foo"

    # There is one pending event.
    pending_events = agg.collect_events()
    assert len(pending_events) == 1

    # The pending event is a created event.
    assert isinstance(pending_events[0], MyAggregate.Created)

    # The created event has a 'name' attribute.
    pending_events[0].name == "foo"

    # The created event can be used to reconstruct the aggregate.
    copy = pending_events[0].mutate(None)
    assert copy.name == agg.name


Dataclass-style init methods
----------------------------

Python's dataclass annotations can be used to define an aggregate's
``__init__()`` method. A created event class can be automatically
defined from this method.

.. code:: python

    from dataclasses import dataclass

    @dataclass
    class MyAggregate(Aggregate):
        name: str


    # Create a new aggregate.
    agg = MyAggregate(name="foo")

    # The aggregate has a 'name' attribute
    assert agg.name == "foo"

    # The created event has a 'name' attribute.
    pending_events = agg.collect_events()
    pending_events[0].name == "foo"


Optional arguments can be defined by providing default
values on the dataclass attribute definitions.

.. code:: python

    from dataclasses import dataclass

    @dataclass
    class MyAggregate(Aggregate):
        name: str = "bar"


    # Call the class without a name.
    agg = MyAggregate()
    assert agg.name == "bar"

    # Call the class with a name.
    agg = MyAggregate("foo")
    assert agg.name == "foo"

Anything that works on a dataclass should work here too. For example,
you can define non-init argument attributes by using the ``field``
feature of the dataclasses module.

.. code:: python

    from dataclasses import field
    from typing import List

    @dataclass
    class MyAggregate(Aggregate):
        history: List[str] = field(default_factory=list, init=False)


    # Create a new aggregate.
    agg = MyAggregate()

    # The aggregate has a list.
    assert agg.history == []


Please note, when using the dataclass-style for defining ``__init__()``
methods, using the :data:`@dataclass` decorator will inform your IDE of
the method signature. The annotations will in any case be used to create
an ``__init__()`` method when the class does not already have an ``__init__()``.
Using the dataclass decorator merely enables code completion and syntax
checking, but the code will run just the same with or without the
:data:`@dataclass` decorator being applied to aggregate classes that
are defined using this style.



Declaring the created event class name
--------------------------------------

To give the created event class a particular name, use the class argument 'created_event_name'.

.. code:: python

    class MyAggregate(Aggregate, created_event_name="Started"):
        name: str

    # Create a new aggregate.
    agg = MyAggregate("foo")

    # The created event class is called "Started".
    pending_events = agg.collect_events()
    assert isinstance(pending_events[0], MyAggregate.Started)


This is equivalent to declaring the created event class explicitly
on the aggregate class using a particular name.

.. code:: python

    class MyAggregate(Aggregate):
        class Started(Aggregate.Created):
            pass

    # Create a new aggregate.
    agg = MyAggregate()

    # The created event class is called "Started".
    pending_events = agg.collect_events()
    assert isinstance(pending_events[0], MyAggregate.Started)


If more than one created event class is defined on the aggregate class, perhaps
because the name of the created event class was changed and there are stored events
that were created using the old created event class that still need to be supported,
the ``created_event_name`` class argument can be used to identify which created event
class is the one to use when creating new aggregate instances. This can be combined
with upcasting old events, discussed above.

.. code:: python

    class MyAggregate(Aggregate, created_event_name="Started"):
        class Created(Aggregate.Created):
            pass

        class Started(Aggregate.Created):
            pass


    # Create a new aggregate.
    agg = MyAggregate()

    # The created event class is called "Started".
    pending_events = agg.collect_events()
    assert isinstance(pending_events[0], MyAggregate.Started)


If the ``created_event_name`` argument is used but the value does not match
the name of one the created event classes that are explicitly defined on the
aggregate class, then an event class will be automatically defined, and it
will be used when creating new aggregate instances.

.. code:: python

    class MyAggregate(Aggregate, created_event_name="Opened"):
        class Created(Aggregate.Created):
            pass

        class Started(Aggregate.Created):
            pass


    # Create a new aggregate.
    agg = MyAggregate()

    # The created event class is called "Opened".
    pending_events = agg.collect_events()
    assert isinstance(pending_events[0], MyAggregate.Opened)


Defining the aggregate ID
-------------------------

By default, the aggregate ID will be a version 4 UUID, automatically
generated when a new aggregate is created. However, the aggregate ID
can also be defined as a function of the arguments used to create the
aggregate. You can do this by defining a ``create_id()`` method.

.. code:: python

    class MyAggregate(Aggregate):
        name: str

        @staticmethod
        def create_id(name: str):
            return uuid5(NAMESPACE_URL, f"/my_aggregates/{name}")


    # Create a new aggregate.
    agg = MyAggregate(name="foo")
    assert agg.name == "foo"

    # The aggregate ID is a version 5 UUID.
    assert agg.id == MyAggregate.create_id("foo")

If a ``create_id()`` method is defined on the aggregate class, the base class
method :func:`~eventsourcing.domain.MetaAggregate.create_id`
will be overridden. The arguments used in this method must be a subset of the
arguments used to create the aggregate. The base class method simply returns a
version 4 UUID, which is the default behaviour for generating aggregate IDs.

Alternatively, an 'id' attribute can be declared on the aggregate
class, and an ID supplied directly when creating new aggregates.

.. code:: python

    def create_id(name: str):
        return uuid5(NAMESPACE_URL, f"/my_aggregates/{name}")

    class MyAggregate(Aggregate):
        id: UUID


    # Create an ID.
    agg_id = create_id(name="foo")

    # Create an aggregate with the ID.
    agg = MyAggregate(id=agg_id)
    assert agg.id == agg_id


When defining an explicit ``__init__()`` method, the ``id`` argument can
be set on the object as ``self._id``. Assigning to ``self.id`` won't work
because ``id`` is defined as a read-only property on the base aggregate class.

.. code:: python

    class MyAggregate(Aggregate):
        def __init__(self, id: UUID):
            self._id = id


    # Create an aggregate with the ID.
    agg = MyAggregate(id=agg_id)
    assert agg.id == agg_id



The :data:`@event` decorator
----------------------------

A more concise way of expressing the concerns around defining, triggering and
applying subsequent aggregate events can be achieved by using the library function
:func:`~eventsourcing.domain.event` to decorate aggregate command methods.

When decorating a method with the :data:`@event` decorator, the method signature
will be used to automatically define an aggregate event class. And when the
method is called, the event will firstly be triggered with the values given
when calling the method, so that an event is created and used to mutate the
state of the aggregate. The body of the decorated method will be used as the
``apply()`` method of the event both after the event has been triggered and
when the aggregate is reconstructed from stored events. The name of the event
class can be passed to the decorator.

.. code:: python

    from eventsourcing.domain import event

    class MyAggregate(Aggregate):
        name: str

        @event("NameUpdated")
        def update_name(self, name):
            self.name = name


    # Create an aggregate.
    agg = MyAggregate(name="foo")
    assert agg.name == "foo"

    # Update the name.
    agg.update_name("bar")
    assert agg.name == "bar"

    # There are two pending events.
    pending_events = agg.collect_events()
    assert len(pending_events) == 2
    assert pending_events[0].name == "foo"

    # The second pending event is a 'NameUpdated' event.
    assert isinstance(pending_events[1], MyAggregate.NameUpdated)

    # The second pending event has a 'name' attribute.
    assert pending_events[1].name == "bar"


Inferring the event class name from the method name
---------------------------------------------------

The :data:`@event` decorator can be used without providing
the name of an event. If the decorator is used without any
arguments, the name of the event will be derived from the
method name. The method name is assumed to be lower case
and underscore-separated. The name of the event class is
constructed by firstly splitting the name of the method by its
underscore characters, then by capitalising the resulting parts,
and then by concatenating the capitalised parts to give an
"upper camel case" class name. For example, a method name
``name_updated`` would give an event class name ``NameUpdated``.


.. code:: python

    from eventsourcing.domain import event

    class MyAggregate(Aggregate):
        name: str

        @event
        def name_updated(self, name):
            self.name = name


    # Create an aggregate.
    agg = MyAggregate(name="foo")
    assert agg.name == "foo"

    # Update the name.
    agg.name_updated("bar")
    assert agg.name == "bar"

    # There are two pending events.
    pending_events = agg.collect_events()
    assert len(pending_events) == 2
    assert pending_events[0].name == "foo"

    # The second pending event is a 'NameUpdated' event.
    assert isinstance(pending_events[1], MyAggregate.NameUpdated)

    # The second pending event has a 'name' attribute.
    assert pending_events[1].name == "bar"

However, this creates a slight tension in the naming conventions
because methods should normally be named using the imperative form
and event names should normally be past participles. However, this
can be useful when naming methods that will be only called by aggregate
command methods under certain conditions.

For example, if an attempt is made to update the value of an attribute,
but the given value happens to be identical to the existing value, then
it might be desirable to skip on having an event triggered.

.. code:: python

    class MyAggregate(Aggregate):
        name: str

        def update_name(self, name):
            if name != self.name:
                self.name_updated(name)

        @event
        def name_updated(self, name):
            self.name = name

    # Create an aggregate.
    agg = MyAggregate(name="foo")
    assert agg.name == "foo"

    # Update the name lots of times.
    agg.update_name("foo")
    agg.update_name("foo")
    agg.update_name("foo")
    agg.update_name("bar")
    agg.update_name("bar")
    agg.update_name("bar")
    agg.update_name("bar")

    # There are two pending events (not eight).
    pending_events = agg.collect_events()
    assert len(pending_events) == 2, len(pending_events)


Using an explicitly defined event class
---------------------------------------

Of course, you may wish to define event classes explicitly. You
can refer to the event class in the decorator, rather than using
a string. The synonymous decorator :data:`@triggers` can be used
instead of the :data:`@event` decorator (it does the same thing).


.. code:: python

    from eventsourcing.domain import triggers

    class MyAggregate(Aggregate):
        name: str

        class NameUpdated(Aggregate.Event):
            name: str

        @triggers(NameUpdated)
        def update_name(self, name):
            self.name = name


    # Create an aggregate.
    agg = MyAggregate(name="foo")
    assert agg.name == "foo"

    # Update the name.
    agg.update_name("bar")
    assert agg.name == "bar"

    # There are two pending events.
    pending_events = agg.collect_events()
    assert len(pending_events) == 2
    assert pending_events[0].name == "foo"

    # The second pending event is a 'NameUpdated' event.
    assert isinstance(pending_events[1], MyAggregate.NameUpdated)

    # The second pending event has a 'name' attribute.
    assert pending_events[1].name == "bar"



The World aggregate class revisited
-----------------------------------

Using the declarative syntax described above, the ``World`` aggregate in
the :ref:`example <Aggregate simple example>` above can be
expressed more concisely in the following way.

In the example below, the ``World`` aggregate's created event is automatically
defined by inspecting the aggregate's ``__init__()`` method. The created event
is named ``Created``. The ``World.SomethingHappened`` event is automatically
defined by inspecting the decorated ``make_it_so()`` method. The event class
name "SomethingHappened" is given to the event decorator. The body of the decorated
``make_it_so()`` method will be used as the ``apply()`` method of the
``World.SomethingHappened`` event, both when the event is triggered and
when the aggregate is reconstructed from stored events.

.. code:: python

    from eventsourcing.domain import event


    class World(Aggregate):
        def __init__(self):
            self.history = []

        @event("SomethingHappened")
        def make_it_so(self, what):
            self.history.append(what)


The ``World`` aggregate class can be called directly. Calling the
class directly will call the :class:`~eventsourcing.domain.Aggregate`
:func:`~eventsourcing.domain.MetaAggregate._create` method with the
automatically defined ``World.Created`` event. Calling the ``make_it_so()``
method will trigger a ``World.SomethingHappened`` event, and this event
will be used to mutate the state of the aggregate, such that the
``make_it_so()`` method argument ``what`` will eventually be appended
to the aggregate's ``history`` attribute.

.. code:: python

    world = World()
    world.make_it_so("dinosaurs")
    world.make_it_so("trucks")
    world.make_it_so("internet")

    assert world.history[0] == "dinosaurs"
    assert world.history[1] == "trucks"
    assert world.history[2] == "internet"
    assert len(world.collect_events()) == 4



The Page and Index aggregates revisited
---------------------------------------

The ``Page`` and ``Index`` aggregates defined in the above
:ref:`discussion about namespaced IDs <Namespaced IDs>` can be expressed more
concisely in the following way.

.. code:: python

    from dataclasses import dataclass


    @dataclass
    class Page(Aggregate):
        name: str
        body: str = ""

        @event("NameUpdated")
        def update_name(self, name: str):
            self.name = name


    @dataclass
    class Index(Aggregate):
        name: str
        ref: Optional[UUID]

        @staticmethod
        def create_id(name: str):
            return uuid5(NAMESPACE_URL, f"/pages/{name}")

        @event("RefUpdated")
        def update_ref(self, ref: Optional[UUID]):
            self.ref = ref


    # Create new page and index aggregates.
    page = Page(name="Erth")
    index1 = Index(name=page.name, ref=page.id)

    # The page name can be used to recreate
    # the index ID. The index ID can be used
    # to retrieve the index aggregate, which
    # gives the page ID, and then the page ID
    # can be used to retrieve the page aggregate.
    index_id = Index.create_id(name="Erth")
    assert index_id == index1.id
    assert index1.ref == page.id
    assert index1.name == page.name

    # Later, the page name can be updated,
    # and a new index created for the page.
    page.update_name(name="Earth")
    index1.update_ref(ref=None)
    index2 = Index(name=page.name, ref=page.id)

    # The new page name can be used to recreate
    # the new index ID. The new index ID can be
    # used to retrieve the new index aggregate,
    # which gives the page ID, and then the page
    # ID can be used to retrieve the renamed page.
    index_id = Index.create_id(name="Earth")
    assert index_id == index2.id
    assert index2.ref == page.id
    assert index2.name == page.name



Non-trivial command methods
---------------------------

Tn the examples above, the work of the command methods is "trivial", in
that the command method arguments are always used directly as the aggregate event
attribute values. But often a command method needs to do some work before
triggering an event. The event attributes may not be the same as the command
method arguments. The logic of the command may be such that under some conditions
an event should not be triggered.

As a final example, consider the following ``Order`` class. It is an ordinary
Python object class. Its ``__init__()`` method takes a ``name`` argument. The
method ``confirm()`` sets the attribute ``confirmed_at``. The method
``pickup()`` checks that the order has been confirmed before calling
the ``_pickup()`` method which sets the attribute ``pickedup_at``.
If the order has not been confirmed, an exception will be raised. That is,
whilst the ``confirm()`` command method is trivial in that its arguments
are always used as the event attributes, the ``pickup()`` method is non-trivial
in that it will only trigger an event if the order has been confirmed. That
means we can't decorate the ``pickup()`` method with the :data:`@event` decorator
without triggering an unwanted event.

.. code:: python

    class Order:
        def __init__(self, name):
            self.name = name
            self.confirmed_at = None
            self.pickedup_at = None

        def confirm(self, at):
            self.confirmed_at = at

        def pickup(self, at):
            if self.confirmed_at:
                self._pickup(at)
            else:
                raise RuntimeError("Order is not confirmed")

        def _pickup(self, at):
            self.pickedup_at = at


This ordinary Python class can used in the usual way. We can construct
a new instance of the class, and call its command methods.

.. code:: python

    # Start a new order, confirm, and pick up.
    order = Order("my order")

    try:
        order.pickup(datetime.now())
    except RuntimeError:
        pass
    else:
        raise AssertionError("shouldn't get here")

    order.confirm(datetime.now())
    order.pickup(datetime.now())

This ordinary Python class can be easily converted into an event sourced aggregate
by applying the library's :data:`@event` decorator to the
``confirm()`` and ``_pickup()`` methods.

Because the command methods are decorated in this way, when the ``confirm()``
method is called, an ``Order.Confirmed`` event will be triggered. When the
``_pickup()`` method is called, an ``Order.PickedUp`` event will be triggered.
Those event classes are defined automatically from the method signatures. The
decorating of the ``_pickup()`` method and not of the ``pickup()`` method is
a good example of a command method that needs to do some work before an event
is triggered. The body of the ``pickup()`` method is only executed when the
command method is called, whereas the body of the ``_pickup()`` method is
executed each time the event is applied to evolve the state of the aggregate.

.. code:: python

    class Order(Aggregate):
        def __init__(self, name):
            self.name = name
            self.confirmed_at = None
            self.pickedup_at = None

        @event("Confirmed")
        def confirm(self, at):
            self.confirmed_at = at

        def pickup(self, at):
            if self.confirmed_at:
                self._pickup(at)
            else:
                raise RuntimeError("Order is not confirmed")

        @event("PickedUp")
        def _pickup(self, at):
            self.pickedup_at = at


We can use the event sourced ``Order`` aggregate in the same way as the undecorated
ordinary Python ``Order`` class. The event sourced version has the advantage
that using it will trigger a sequence of aggregate events that can be persisted in
a database and used in future to determine the state of the order.

.. code:: python

    order = Order("my order")
    order.confirm(datetime.now())
    order.pickup(datetime.now())

    # Check the state of the order.
    assert order.name == "my order"
    assert isinstance(order.confirmed_at, datetime)
    assert isinstance(order.pickedup_at, datetime)
    assert order.pickedup_at > order.confirmed_at

    # Check the triggered events determine the state of the order.
    pending_events = order.collect_events()
    copy = None
    for e in pending_events:
        copy = e.mutate(copy)
    assert copy.name == order.name
    assert copy.created_on == order.created_on
    assert copy.modified_on == order.modified_on
    assert copy.confirmed_at == order.confirmed_at
    assert copy.pickedup_at == order.pickedup_at


Raising exceptions in the body of decorated methods
---------------------------------------------------

It is actually possible to decorate the ``pickup()`` command method
with the :data:`@event` decorator, but if a decorated command method
has conditional logic that would mean the state of the aggregate
should not be evolved, you must take care to raise an exception
rather than returning early, and raise an exception before changing
the state of the aggregate at all. By raising an exception in the body
of a decorated method, the triggered event will not in fact be appended
to the aggregate's list of pending events, and it will be as if it never
happened. However, the conditional expression will be perhaps needlessly
evaluated each time the aggregate is reconstructed from stored events. Of
course this conditional logic may be useful and considered as validation
of the projection of earlier events, for example checking the the ``Confirmed``
event is working properly.

If you wish to use this style, just make sure to raise an exception rather
than returning early, and make sure not to change the state of the aggregate
if an exception may be raised later. Returning early will mean the event
will be appended to the list of pending events. Changing the state before
raising an exception will the state will be different when the aggregate
is reconstructed from stored events. So if your method does change state
and then raise an exception, make sure to obtain a fresh version of the
aggregate before continuing to trigger events.

.. code:: python

    class Order(Aggregate):
        def __init__(self, name):
            self.name = name
            self.confirmed_at = None
            self.pickedup_at = None

        @event("Confirmed")
        def confirm(self, at):
            self.confirmed_at = at

        @event("PickedUp")
        def pickup(self, at):
            if self.confirmed_at:
                self.pickedup_at = at
            else:
                raise RuntimeError("Order is not confirmed")


        # Creating the aggregate causes one pending event.
        order = Order("name")
        assert len(order.pending_events) == 1

        # Call pickup() too early raises an exception.
        try:
            order.pickup(datetime.now())
        except RuntimeError:
            pass
        else:
            raise Exception("Shouldn't get here")

        # There is still only one pending event.
        assert len(order.pending_events) == 1


Recording command arguments and reprocessing them each time the aggregate is
reconstructed is perhaps best described as "command sourcing".

In many cases, a command will do some work and trigger
an aggregate event that has attributes that are different from the command,
and in those cases it is necessary to have two different methods with different
signatures: a command method that is not decorated and a decorated method that
triggers and applies an aggregate event. This second method may arguably be
well named by using a past participle rather than the imperative form.


The :data:`@aggregate` decorator
--------------------------------

Just for fun, the library's :func:`~eventsourcing.domain.aggregate` function can be
used to declare event sourced aggregate classes. This is equivalent to inheriting
from the library's :class:`~eventsourcing.domain.Aggregate` class. The created
event name can be defined using the ``created_event_name`` argument of the decorator.
However, it is recommended to inherit from the :class:`~eventsourcing.domain.Aggregate`
class rather than using the ``@aggregate`` decorator so that full the
:class:`~eventsourcing.domain.Aggregate` class definition will be visible to your IDE.

.. code:: python

    from eventsourcing.domain import aggregate


    @aggregate(created_event_name="Started")
    class Order:
        def __init__(self, name):
            self.name = name


    order = Order("my order")
    pending_events = order.collect_events()
    assert isinstance(pending_events[0], Order.Started)


Initial version number
======================

By default, the aggregates have an initial version number of ``1``. Sometimes it may be
desired, or indeed necessary, to use a different initial version number.

In the example below, the initial version number of the class ``MyAggregate`` is defined to be ``0``.

.. code:: python

    class MyAggregate(Aggregate):
        INITIAL_VERSION = 0

    aggregate = MyAggregate()
    assert aggregate.version == 0


If all aggregates in a domain model need to use the same non-default version number,
then a base class can be defined and used by the aggregates of the domain model on
which ``INITIAL_VERSION`` is set to the preferred value. Some people may wish to set
the preferred value on the library's :class:`~eventsourcing.domain.Aggregate` class.


Timestamp timezones
===================

The timestamp values mentioned above are "timezone aware" Python :class:`datetime` objects,
created by calling :func:`datetime.now`. The default timezone is UTC, as defined by Python's
:data:`datetime.timezone.utc`. It is generally recommended to store date-times as UTC values,
and convert to a local timezone in an interface layer, according to the particular timezone
of a particular user. However, if necessary, this default can be changed by assigning a
:class:`datetime.tzinfo` object to the :data:`TZINFO` attribute of the
:mod:`eventsourcing.domain` module. The :data:`eventsourcing.domain.TZINFO`
value can also be configured using environment variables, by setting the environment variable
``TZINFO_TOPIC`` to a string that describes the :ref:`topic <Topics>` of a Python
:data:`datetime.tzinfo` object (for example ``'datetime:timezone.utc'``).


.. _Topics:

Topic strings
=============

A "topic" in this library is a string formed from joining with a colon character
(``':'``) the path to a Python module (e.g. ``'eventsourcing.domain'``) with the qualified
name of an object in that module (e.g. ``'Aggregate.Created'``). For example
``'eventsourcing.domain:Aggregate.Created'`` is the topic of the library's
:class:`~eventsourcing.domain.Aggregate.Created` class. The library's
:mod:`~eventsourcing.utils` module contains the functions :func:`~eventsourcing.utils.resolve_topic`
and :func:`~eventsourcing.utils.get_topic` which are used in the library to resolve
a given topic to a Python object, and to construct a topic for a given Python object.


.. code:: python

    from eventsourcing.utils import get_topic, resolve_topic


    assert get_topic(Aggregate) == "eventsourcing.domain:Aggregate"
    assert resolve_topic("eventsourcing.domain:Aggregate") == Aggregate

    assert get_topic(Aggregate.Created) == "eventsourcing.domain:Aggregate.Created"
    assert resolve_topic("eventsourcing.domain:Aggregate.Created") == Aggregate.Created


Topic strings are used in stored events, to identify its domain event object type,
and in in "created" events to identify the aggregate object type.


Renaming and moving classes
===========================

The :func:`~eventsourcing.utils.register_topic` function
can be used to register an old topic for a class that has
been moved or renamed. When a class is moved or renamed,
unless the old topic can be resolved to the class in its
new location, it won't be possible to reconstruct an event
or aggregate from its stored domain events.

.. code:: python

    from eventsourcing.utils import register_topic


    class MyAggregate(Aggregate):
        pass


    assert get_topic(Aggregate) == "__main__:Aggregate"
    assert resolve_topic("__main__:Aggregate") == Aggregate

    register_topic("oldmodule:PreviousName", MyAggregate)
    assert resolve_topic("oldmodule:MyAggregate") == MyAggregate


Notes
=====

Why put methods on event objects? There has been much discussion about the best way
to define the aggregate projections. Of course, there isn't a "correct" way of doing it,
and alternatives are possible. The reason for settling on the style presented most
prominently in this documentation, where each aggregate event has a method that
defines how it will apply to the aggregate (neatly wrapped up with the
:ref:`declarative syntax <Declarative syntax>`) is the practical reason that it keeps the
parts of projection closest to the event class to which they pertain, and experience has shown
that this makes the domain model core easier to develop and understand. In the first version of
this library, the classical approach to writing domain models described in Martin
Fowler's book *Patterns of Enterprise Application Architecture* was followed, so that
there was a repository object for each class of domain object (or aggregate). If the
type of aggregate is known when the domain object is requested, that is because each
repository was constructed for that type, and so we can understand that these
repositories can be constructed with a particular mutator function that will
function as the aggregate projection for that type. When stored domain events are
retried, this particular mutator function can be called. As the mutator function
will be coded for a particular aggregate, the aggregate class can be coded into
the function to handle the initial event. However, it became cumbersome to
define a new repository each time we define a new aggregate class. And anyway this
classical design for many repositories was, more or less, an encapsulation of the
database tables which were required to support the different types of domain object.
But in an event-sourced application, all the aggregate events are stored in the same
stored events table, and so it suffices to have one repository to encapsulate this
table in an event-sourced application. But the issue which arises is that a single
repository for all aggregates can't know which type of aggregate is being requested
when an aggregate is requested by ID. Of course, it would be possible to pass in the
mutator function when requesting an aggregate, or for the repository more simply to
return a list of aggregate events rather than an aggregate. But if we want a single
repository, and we want it to provide the "dictionary-like interface" that is described
in *Patterns of Enterprise Application Architecture*, so that we give an ID and get an
aggregate, then the issue of identifying the aggregate type remains. To resolve this
issue, we can return to the "headline" definition of event sourcing, which is that
the state is determined by a sequence of events. The events can function to determine
the state of the aggregate by having a aggregate "topic" on the initial event, and by
defining methods on the event classes, methods that project the state of the events into
the state of the aggregate. These methods are as close as possible to the definition of the
event data, and when developing the code we avoid having to scroll around the
to see how an event is applied to an aggregate. Indeed, Martin Fowler's 2005
`event sourcing article <https://martinfowler.com/eaaDev/EventSourcing.html>`_
has a UML diagram which shows exactly this design, with a method called 'process'
on the ShippingEvent class in the section How It Works. A further consideration,
and perhaps criticism of this style, is that this style of writing
projections is special, and other projections will have to be written in a different way.
This is true, but in practice, aggregate events are used overwhelmingly often to reconstruct
the state of aggregates, and in many applications that is the only way they will
be projected. And so, since there is an advantage to coding the aggregate projection
on the aggregate events, that is the way we settled on coding these things. The initial
impetus for coding things this way came from users of the library. The library
documentation was initially written to suggest using a separate mutator function.
However, that isn't the end of the story. There are three outstanding unsettled feelings.
Firstly, by coding the aggregate project on methods of the aggregate, and passing
in the aggregate to this method, there is a reversal of intuition in these methods,
where `self` is the thing that has the data and doesn't change, and changes are
made to a method argument. Secondly, a tension arises between either rudely accessing the
private members of the aggregate, or expanding its public interface that would
be much better restricted to being only an expression of support for the application.
Thirdly, in the process of defining an event class, passing in the arguments to
trigger an event, and then using the event attributes to mutate the aggregate, we
have to say everything three times. At first, we can enjoy being explicit about
everything. But after some time, the desire grows to find a way to say things once.
These three feelings, of an intuitive reversal of setting values from self onto a
method argument, of accessing private members or expanding the public interface, and
of saying everything three times, were resolved by the introduction of the ``@event``
decorator as a more :ref:`declarative syntax <Declarative syntax>`. One criticism
of the declarative syntax design is that it is "command sourcing" and not "event sourcing",
because it is the command method arguments that are being used as the attributes of the
event. If may sometimes be "command sourcing" but then it is certainly also event
sourcing. Applications exist to support a domain, and in many cases applications support
the domain by recording decisions that are made in the domain and received by the domain model.
The ``@event`` decorator can also be used on "private" methods, methods that not part of the
aggregate's "public" command and query interface that will be used by the application, called
by "public" commands which are not so decorated, so do not trigger events that are simply
comprised of the method arguments, so then there is event sourcing" but not command
sourcing. The important thing here is to separate out the work of the command if
indeed there is any work (work that should happen only once) from the definition of
and construction of an aggregate event object, and from the projection
of the aggregate event into the aggregate state (which will happen many times).

Why mutate the aggregate state? Another question that may arise is about mutating the
aggregate object, rather than reconstructing a copy of the aggregate that combines
the old unchanged parts and the new. It is certainly possible to adjust the event classes
so that the original is unchanged. There are a few good reasons for doing this. The issue
is about concurrent access to aggregates that are cached in memory. This library follows
the traditional patterns of having commands which do not return values and of mutating
aggregate objects in-place. The issue of concurrent access doesn't arise unless the aggregates
are cached and used concurrently without any concurrency controls, such as serialisation of
access. Aggregates aren't cached, by default, and so the issue doesn't arise unless they are.
And because it is in the nature of aggregates that they create a sequence of events,
there is no value to allowing concurrent write access. So if aggregates are to be cached
then it would make sense either to implement locking, so that readers don't access a
half-updated state and so that writers don't interact, or for writers to make a deep
copy of a cached aggregate before calling aggregate commands, and then updating the
cache with their mutated version after the aggregate has been successfully saved. And
care would need to be taken to fast-forward an aggregate that is stale because another
process has advanced the state of the aggregate. But none of these issues arise in the
library because aggregates are not cached.

Another issue arises about the use of "absolute" topics to identify classes. The issue
of moving and renaming classes can be resolved by setting the old paths to point to
current classes, using the library's methods for doing this.

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
