==============================================
:mod:`~eventsourcing.domain` --- Domain models
==============================================


This module supports the development of event-sourced domain models.

Following the terminology of *Domain-Driven Design*, an event-sourced domain
model has many event-sourced :ref:`aggregates <Aggregates>`. The state of an
event-sourced aggregate is determined by a sequence of :ref:`aggregate events
<Aggregate events>`. The time needed to reconstruct an aggregate from its domain
events can be reduced by using :ref:`snapshots <Snapshots>`.

The classes in this module were first introduced merely as a way of showing
how the :doc:`persistence module </topics/persistence>` can be used. The
persistence module is the original core of this library, and is the cohesive
mechanism for storing and retrieving sequences ("streams") of immutable events.
But without showing how this mechanism can be used to develop an event-sourced
domain model, there was a gap where application developers expected guidance
and examples, some more solid ground on which to build.

Through a process of refinement over several years, this module has evolved
into a highly effective way of coding event-sourced domain models in Python.
It's possible to develop an event-sourced domain model without using this
module. :ref:`Alternative ways <Example aggregates>` of coding domain models
are certainly possible.

However, if you want to progress rapidly, you may find that using the
:class:`~eventsourcing.domain.Aggregate` class and the :func:`@event<eventsourcing.domain.event>`
decorator will speed your creativity in developing a :ref:`compact and effective <Declarative syntax>`
event-sourced domain model in Python.

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

That is to say, an 'aggregate' is a cluster of 'entities' and 'value objects'.
An 'entity' is an object with a fixed unique identity (an ID) and other attributes
that may vary. A 'value object' does not vary, nor does it necessarily have a
unique identity. The notion of a cluster of software objects is understandable
as straightforward `object-oriented programming
<https://en.wikipedia.org/wiki/Object-oriented_programming>`_.

An aggregate has a 'root'. The 'root' of an aggregate is an entity.
This entity is known as the 'root entity' or the 'aggregate root'. The
ID of the root entity is used to uniquely identify the aggregate in
a domain model. References to the aggregate are references to the aggregate's
root entity.

Access to the aggregate's cluster of objects is made through the aggregate's
root entity. Changes to the aggregate's cluster of objects are decided by
'command methods'. The state of the cluster of objects is accessed using
'query methods'. The aggregate's command and query methods will usually be
defined on the aggregate's root entity.
The idea of distinguishing between command methods (methods that change state but
do not return values) and query methods (methods that return values but do not
change state) is known as 'command-query separation' or CQS. `CQS was devised
by Bertrand Meyer <https://en.wikipedia.org/wiki/Command%E2%80%93query_separation>`_
and described in his book *Object Oriented Software Construction*.

The extent of the cluster of objects defines the 'boundary' of the aggregate.
The 'consistency' of the cluster of objects is maintained by making sure all
the changes that result from a single command are `recorded atomically
<https://en.wikipedia.org/wiki/Atomicity_(database_systems)>`_. These two notions
of 'consistency' and 'boundary' are combined in the notion in *Domain-Driven
Design* of 'consistency boundary'. Whilst we can recognise a cluster of software
objects as basic object-orientated programming, and the use of command and query
methods as the more refined pattern called CQS, the 'consistency boundary' notion
gives aggregates of *Domain-Driven Design* their distinctive character.

What is this distinctive character? The state of an aggregate is determined by the state
of its cluster of entities and value objects. There is only ever one cluster of objects
for any given aggregate, so there is no branching of the state of an aggregate. Therefore,
the atomic changes decided by an aggregate's command methods must have a serial order.
Constructing a serially ordered sequence of decisions for a cluster of domain model objects
gives the notion 'consistency boundary' its meaning. Furthermore, the distinctive character
of the domain models of *Domain-Driven Design* is the generation of many serially ordered
sequences of decisions, because they are comprised of many aggregates. By comparison, the
domain model pattern in Martin Fowler's *Patterns of Enterprise Application Architecture* does
not propose this degree of order in its society of decisions.

If *Domain-Driven Design* is a general approach to creating domain models
for any domain, that is because the structure 'many individual sequences of decisions'
is generally adequate and applicable for analysis and design. To understand this in general,
we can use Alfred North Whitehead's process-philosophical scheme, which is explained most
fully in his famous book *Process and Reality*. The term 'domain model' in
*Domain-Driven Design* corresponds to the notion 'corpuscular society' in Whitehead's scheme.
The term 'aggregate' in  *Domain-Driven Design* corresponds to the notion 'enduring object' in
Whitehead's scheme. A corpuscular society is said to comprise many strands of enduring object.
An enduring object is said to have 'personal order'. A sequence of decisions corresponds to
Whitehead's notion of 'personal order'. The term 'domain event' corresponds the notion
'actual entity' (also known as 'actual occasion'). An actual occasion in Whitehead's scheme
is the creative process of becoming in which many previous decisions are 'felt' and in which
these feelings are grown together into a complex unity of feeling that decides what the actual
occasion will be (its decision).

This isn't the place to discuss Whitehead's scheme in great detail,
however it is worth noting that Whitehead proposes these terms in his categories
of existence, and proposes this general structure as being adequate and applicable
for analysing (and therefore for designing) the ordinary objects we may encounter
in the world.

    *An ordinary physical object, which has temporal endurance, is a society
    [of 'actual occasions' or 'actual entities']. In the ideally simple case,
    it has personal [serial] order and is an 'enduring object'. A society may
    (or may not) be analysable into many strands of 'enduring objects'. This
    will be the case for most ordinary physical objects. These enduring objects
    and 'societies' analysable into strands of enduring objects, are the permanent
    entities which enjoy adventures of change throughout time and space. For example,
    they form the subject-matter of the science of dynamics. Actual entities perish,
    but do not change; they are what they are. A nexus which (i) enjoys social order,
    and (ii) is analysable into strands of enduring objects may be termed a
    'corpuscular society'.*

We know that Whitehead's scheme was enormously influential for Christopher Alexander
when inventing his pattern language scheme. And we know that Christopher Alexander's
scheme was enormously influential for Eric Evans when writing *Domain-Driven Design*.
What wasn't known by Eric Evans was the influence of Whitehead's scheme on Alexander's
work. Nevertheless, something of Whitehead's scheme has been carried through this
chain of influence, and the appearance in software development of a general model
that involves many strands of enduring objects as the structure of analysis and design
is, in my understanding, the primary way in which *Domain-Driven Design* constitutes a
novel and important advance for the development of domain models in software.

.. _Aggregates:

Event-sourced aggregates
========================

It is in the `Zen of Python <https://www.python.org/dev/peps/pep-0020/>`_ that
explicit is better than implicit. The changes to an aggregate's
cluster of objects will always follow from decisions made by the aggregate.
It will always be true that a decision itself, having happened, does not change.
But the results of such a decision are not always expressed explicitly as an
immutable event object. Conventional applications update records of this objects
in-place as a result of those decisions.  For example, consider a bank account with a
starting balance of £100.  A debit transaction for £20 then occurs, resulting in a
new balance of £80. That might be coded as follows:

.. code-block:: python

    class BankAccount:
        def __init__(self, starting_balance: int):
            self.balance = starting_balance

        def debit(self, amount):
            self.balance = self.balance - amount


    account = BankAccount(100)
    account.debit(20)

    assert account.balance == 80

Note that the *event* --- the reason that the balance changed from 100 to 80 --- is
transient.  It has a brief existence in the time it takes the ``debit()`` method
to execute, but then is lost.  The debit decision itself is implicit; it has no
durable existence. Event-sourced aggregates make these things explicit.

.. pull-quote::

    *"Explicit is better than implicit."*


To make things explicit, a decision made in the command method of an
aggregate can be coded and recorded as an immutable 'domain event'
object, and this object can be used to evolve the state of the aggregate.
For example, bank account balances are derived from a sequence of
transactions. In general, for each event-sourced aggregate, there will
a sequence of domain event objects, and the state of an event-sourced
aggregate will be determined by this sequence. The state of an aggregate
can change, and its sequence of domain events can be augmented. But once
they have been created, the individual domain event objects do not change.
They are what they are.

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

Generally speaking, method names should use the imperative mood, and event class
names should use past participles (regular or irregular).


.. _Domain events:

Domain events
-------------

Domain event objects are created but do not change.

To model the immutable character of a domain event, the library's metaclass
:class:`~eventsourcing.domain.MetaDomainEvent` ensures that all classes
of this type are implemented as `frozen Python data classes
<https://docs.python.org/3/library/dataclasses.html#frozen-instances>`_.
That is, annotations on such classes are used to define object instance
attributes, and these attributes cannot be assigned new values after the
object instance has been constructed.

.. code-block:: python

    from eventsourcing.domain import MetaDomainEvent

The library's :class:`~eventsourcing.domain.DomainEvent` class is a base
class for domain events, which has :class:`~eventsourcing.domain.MetaDomainEvent`
as its metaclass.

.. code-block:: python

    from eventsourcing.domain import DomainEvent

    assert isinstance(DomainEvent, MetaDomainEvent)

A :class:`~eventsourcing.domain.DomainEvent` object has three attributes.

It has an :py:attr:`~eventsourcing.domain.DomainEvent.originator_id`,
which is a Python :class:`~uuid.UUID` that identifies an aggregate
or sequence (or "stream") to which the domain event belongs.

It has an :py:attr:`~eventsourcing.domain.DomainEvent.originator_version`,
which is a Python :class:`int`, which represents its position in that sequence.

It has a :py:attr:`~eventsourcing.domain.DomainEvent.timestamp` attribute,
which is a Python :class:`~datetime.datetime` that represents the date and
time when the event occurred.

The :class:`~eventsourcing.domain.DomainEvent` class can be instantiated directly.

.. code-block:: python

    from datetime import datetime
    from uuid import uuid4

    originator_id = uuid4()

    domain_event = DomainEvent(
        originator_id=originator_id,
        originator_version=2,
        timestamp=datetime(2022, 2, 2),
    )
    assert domain_event.originator_id == originator_id
    assert domain_event.originator_version == 2
    assert domain_event.timestamp == datetime(2022, 2, 2)


The :class:`~eventsourcing.domain.DomainEvent` class also has a static method
:func:`~eventsourcing.domain.DomainEvent.create_timestamp` which returns a
new timezone-aware Python :class:`~datetime.datetime` for the current date and time.
This method is used in various places in the library to
create the :py:attr:`~eventsourcing.domain.DomainEvent.timestamp` value of new domain event objects.

.. code-block:: python

    timestamp = DomainEvent.create_timestamp()

    assert isinstance(timestamp, datetime)

The timestamps have no consequences for the operation of this library, and
are included to give an approximate indication of when a domain event occurred.
Domain event objects are ordered in their sequence by their
:py:attr:`~eventsourcing.domain.DomainEvent.originator_version`, and not by their
:py:attr:`~eventsourcing.domain.DomainEvent.timestamp`. The reason for ordering a sequence of events by
:py:attr:`~eventsourcing.domain.DomainEvent.originator_version` and not
:py:attr:`~eventsourcing.domain.DomainEvent.timestamp` is that the integer
version numbers can form a gapless sequence, that excludes the possibility
for inserting new items anywhere other than at the end of the sequence, and
that we can progress along by counting. Timestamps are far more likely to have
such gaps, and anyway can suffer from clock skews, for example if the timestamps
of different events are created on different machines.


.. _Aggregate events:

Aggregate events
----------------

Aggregate events represent original decisions made in a domain model that advance
the state of its aggregates.

Broadly speaking, there are three kinds of aggregate events: "created" events,
"subsequent" events, and "discarded" events. In this library, the base class
:class:`~eventsourcing.domain.AggregateEvent` is the common superclass of
all three kinds of aggregate events.

We will discuss aggregate objects in more detail below, but for the purpose
of discussing aggregate events, an aggregate object is expected to
have these four attributes:
:py:obj:`~eventsourcing.domain.Aggregate.id`,
:py:obj:`~eventsourcing.domain.Aggregate.version`,
:py:obj:`~eventsourcing.domain.Aggregate.created_on` and
:py:obj:`~eventsourcing.domain.Aggregate.modified_on`.

The class ``A`` defined below will suffice for this purpose.

.. code-block:: python

    class A:
        def __init__(self, id, version, created_on):
            self.id = id
            self.version = version
            self.created_on = created_on
            self.modified_on = created_on


The library's :class:`~eventsourcing.domain.AggregateEvent`
class is defined as a subclass of :class:`~eventsourcing.domain.DomainEvent`.
It is therefore a frozen data class.

.. code-block:: python

    from eventsourcing.domain import AggregateEvent

The :class:`~eventsourcing.domain.AggregateEvent` class can be instantiated directly.

.. code-block:: python

    aggregate_event = AggregateEvent(
        originator_id=originator_id,
        originator_version=2,
        timestamp=datetime(2022, 2, 2),
    )
    assert aggregate_event.originator_id == originator_id
    assert aggregate_event.originator_version == 2
    assert aggregate_event.timestamp == datetime(2022, 2, 2)


The :class:`~eventsourcing.domain.AggregateEvent` class extends
:class:`~eventsourcing.domain.DomainEvent` by inheriting two methods
from the class :class:`~eventsourcing.domain.CanMutateAggregate`:
:func:`~eventsourcing.domain.CanMutateAggregate.mutate` and
:func:`~eventsourcing.domain.CanMutateAggregate.apply`.

Although the :class:`~eventsourcing.domain.AggregateEvent` class can be
instantiated directly, it is not usually used in this way. More typically,
subclasses are defined to code specifically for the particular decisions
made by an aggregate.

The :func:`~eventsourcing.domain.CanMutateAggregate.mutate` method has
an ``aggregate`` argument. Both the ``aggregate`` argument and the return
value are typed as ``Optional``. This allows for three useful kinds of
subclasses of :class:`~eventsourcing.domain.AggregateEvent` to all have
the same method signature. "Created" events expect the ``aggregate`` argument
to be ``None`` and will return a new aggregate object. "Subsequent" events
expect the ``aggregate`` argument to be an aggregate object and will usually
return a modified aggregate object. "Discarded" events also expect the ``aggregate``
argument to be an aggregate object, but will usually return ``None``.


.. _Aggregate created events:

Aggregate "created" events
--------------------------

The mutate method on "created" events expects the value of the ``aggregate``
argument to be ``None``. It will return a new aggregate object.

The library has an :class:`~eventsourcing.domain.AggregateCreated` class which
represents the initial creation of an aggregate, and can be extended to define
particular "created" events in your model.

.. code-block:: python

    from eventsourcing.domain import AggregateCreated


It is implemented as a frozen data class, that inherits and extends the
:class:`~eventsourcing.domain.AggregateEvent` class.

It defines an :py:attr:`~eventsourcing.domain.AggregateCreated.originator_topic` attribute,
which is a Python :class:`str`. The value of the :py:attr:`~eventsourcing.domain.AggregateCreated.originator_topic`
attribute will be a :ref:`topic <Topics>` that describes the path to an aggregate class.

It inherits from the :func:`~eventsourcing.domain.CanInitAggregate` class, and uses its
:func:`~eventsourcing.domain.CanInitAggregate.mutate` method, which can construct the initial
state of an aggregate. This method's ``aggregate`` argument is expected to be ``None``. This
method resolves the :py:attr:`~eventsourcing.domain.AggregateCreated.originator_topic` attribute
to an :class:`~eventsourcing.domain.Aggregate` class, and then constructs an instance
from the class. It then calls :func:`~eventsourcing.domain.Aggregate.__base_init__`
on the newly constructed :class:`~eventsourcing.domain.Aggregate` instance.

So that we avoid the "boiler plate" of all aggregate subclasses mentioning
the same list of common attributes as arguments in the signatures of their
``__init__`` methods, and so that we avoid these ``__init__`` methods always
having to call their super class ``__init__`` method with these common arguments,
the method :func:`~eventsourcing.domain.Aggregate.__base_init__` is defined to expect
those common attribute values as its arguments. The :func:`~eventsourcing.domain.CanInitAggregate.mutate`
method uses the values of the event attributes
:py:attr:`~eventsourcing.domain.DomainEvent.originator_id`,
:py:attr:`~eventsourcing.domain.DomainEvent.originator_version`, and
:py:attr:`~eventsourcing.domain.DomainEvent.timestamp` as the values of these arguments.
The :func:`~eventsourcing.domain.Aggregate.__base_init__` method then initialises
the aggregate's
:py:obj:`~eventsourcing.domain.Aggregate.id`,
:py:obj:`~eventsourcing.domain.Aggregate.version`,
:py:obj:`~eventsourcing.domain.Aggregate.created_on` and
:py:obj:`~eventsourcing.domain.Aggregate.modified_on` attributes using these values.

After calling :func:`~eventsourcing.domain.Aggregate.__base_init__`,
the :func:`~eventsourcing.domain.CanInitAggregate.mutate` method then calls
the aggregate's ``__init__`` method with any remaining event object attributes,
and then returns the newly constructed aggregate object to the caller. The aggregate's
``__init__`` method is expected to be defined with matching arguments.

In the example below, the :class:`~eventsourcing.domain.AggregateCreated` is constructed
directly. This results in a "created" event object. The :func:`~eventsourcing.domain.CanInitAggregate.mutate`
method is called on this event object. This results in a new aggregate object. The values
of the attributes of the aggregate object follow from the values of the event object's constructor
arguments

.. code-block:: python

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
    assert a.created_on == datetime(2011, 1, 1)
    assert a.modified_on == datetime(2011, 1, 1)


"Subsequent" aggregate events
-----------------------------

Subsequent events are events after the "created" event in an aggregate sequence.

The mutate method on "subsequent" events expects the value of the ``aggregate``
argument to be an aggregate object. It will return a modified aggregate object.

The :func:`~eventsourcing.domain.CanMutateAggregate.mutate` method has
an ``aggregate`` argument. Although the ``aggregate`` argument of
:func:`~eventsourcing.domain.CanMutateAggregate.mutate` methods is
typed as an optional argument, the value given when this method is
called is expected to be an aggregate and not ``None``.

When :func:`~eventsourcing.domain.CanMutateAggregate.mutate` is called
on an aggregate event object, several operations are performed.

Firstly, the event is validated against the state of the aggregate. If the
event's :py:attr:`~eventsourcing.domain.DomainEvent.originator_id` does not
equal the aggregate object's :py:obj:`~eventsourcing.domain.Aggregate.id`,
then an :class:`~eventsourcing.domain.OriginatorIDError` is raised. And
if the event's :py:attr:`~eventsourcing.domain.DomainEvent.originator_version`
is not one greater than the aggregate's :py:obj:`~eventsourcing.domain.Aggregate.version`,
then an :class:`~eventsourcing.domain.OriginatorVersionError` exception is raised.

If the validation is successful, the event object's
:func:`~eventsourcing.domain.CanMutateAggregate.apply` method is called.
The :func:`~eventsourcing.domain.CanMutateAggregate.apply` method is called
after the validation checks and before modifying the aggregate's state, so
that if it raises an exception, then the aggregate will remain unmodified
by the :func:`~eventsourcing.domain.CanMutateAggregate.mutate` method.

Then, the aggregate's :py:obj:`~eventsourcing.domain.Aggregate.version`
is then incremented and the event's :py:attr:`~eventsourcing.domain.DomainEvent.timestamp` is assigned to the aggregate's
:py:obj:`~eventsourcing.domain.Aggregate.modified_on` property.

The modified aggregate is then returned to the caller.

.. code-block:: python

    a = A(
        id=originator_id,
        version=1,
        created_on=datetime(2011, 1, 1)
    )

    assert a.id == originator_id
    assert a.version == 1
    assert a.modified_on == datetime(2011, 1, 1)

    a = aggregate_event.mutate(a)

    assert a.id == originator_id
    assert a.version == 2
    assert a.modified_on == datetime(2022, 2, 2)


The :func:`~eventsourcing.domain.CanMutateAggregate.apply` method has
a non-optional ``aggregate`` argument. This method does nothing
but exist to be overridden as a convenient way for users to define
how a particular event evolves the state of a particular aggregate.

.. code-block:: python

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



The object returned by calling the :func:`~eventsourcing.domain.CanMutateAggregate.mutate`
method on one aggregate event object can be passed in when calling the same method on
another aggregate event object. In this way, the :func:`~eventsourcing.domain.CanMutateAggregate.mutate`
methods of a sequence of aggregate event objects can be used successively to reconstruct
the current state of an aggregate.

.. code-block:: python

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


Hence, the :func:`~eventsourcing.domain.CanMutateAggregate.mutate` and
:func:`~eventsourcing.domain.CanMutateAggregate.apply` methods of aggregate events
can be used effectively to implement an "aggregate projector", a "mutator function"
by which the state of an aggregate will be reconstructed from its history of events.

In the example below, the function ``reconstruct_aggregate_from_events()`` implements
an aggregate projector by iterating over a sequence of events and calling
:func:`~eventsourcing.domain.CanMutateAggregate.mutate` on each.

.. code-block:: python

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


This is essentially how the :func:`~eventsourcing.application.Repository.get`
method of an :ref:`application repository <Repository>` reconstructs an aggregate
from stored events when the aggregate is requested by ID.

The ``aggregate`` argument and return value of
the event :func:`~eventsourcing.domain.CanMutateAggregate.mutate` method are optional,
so that this method can implemented on subclasses in various ways. In particular,
"created" events can be defined to accept ``None`` and return a newly constructed
aggregate object, subsequent aggregate events can be defined to accept an aggregate
object and return a modified aggregate object, and "discarded" events can be defined
to accept an aggregate object and return ``None``.

"Discarded" events
------------------

"Discarded" events are usually the last subsequent event in an aggregate sequence.

The mutate method on "discarded" events expects the value of the ``aggregate``
argument to be an aggregate object, but will return ``None``.

If you need to model aggregates being "deleted" or "discarded" (perhaps so that they no
longer appear to exist in an application repository) then it is possible to subclass
the :class:`~eventsourcing.domain.AggregateEvent` class and override the
:func:`~eventsourcing.domain.CanMutateAggregate.mutate` with a method that returns ``None``.

In the example below, an ``AggregateDiscarded`` event class is defined with a ``mutate()``
method that returns ``None``. A "discarded" event object is constructed using this class.
This event object is appended to the list of ``events`` from the examples above. This list
of events is then used to reconstruct the "current state" of the aggregate. The result is
``None``.

.. code-block:: python

    class AggregateDiscarded(AggregateEvent):
        def mutate(self, aggregate):
            super().mutate(aggregate)
            return None


    aggregate_discarded = AggregateDiscarded(
        originator_id=originator_id,
        originator_version=4,
        timestamp=datetime(2044, 4, 4),
    )


    events.append(aggregate_discarded)

    a = reconstruct_aggregate_from_events(events)

    assert a is None

Although the library does not provide any "discarded" event classes, if you need
to model an aggregate such that it eventually appears no longer to exist in an
application repository, you can adapt this technique for your situation. For example,
you may wish to define an attribute such as ``is_discarded``, which is initially ``False``
but is set ``True`` in the "discarded" event's ``mutate()`` method, and then test the value
of this attribute in aggregate command methods and raise an exception if the aggregate
has been discarded.


Aggregate base class
--------------------

This library's :class:`~eventsourcing.domain.Aggregate` class is a base class for
event-sourced aggregates. It can be used to develop event-sourced aggregates.

.. code-block:: python

    from eventsourcing.domain import Aggregate


For convenience, the
:class:`~eventsourcing.domain.Aggregate` class has a nested :class:`Aggregate.Event <eventsourcing.domain.Aggregate.Event>` class.
It is defined as a subclass of :class:`~eventsourcing.domain.AggregateEvent`.

.. code-block:: python

    assert issubclass(Aggregate.Event, AggregateEvent)


The :class:`~eventsourcing.domain.Aggregate` class also has a nested :class:`Aggregate.Created <eventsourcing.domain.Aggregate.Created>` class.
It is defined as a subclass of :class:`~eventsourcing.domain.AggregateCreated`  and
:class:`Aggregate.Event <eventsourcing.domain.Aggregate.Event>`.

.. code-block:: python

    assert issubclass(Aggregate.Created, AggregateCreated)
    assert issubclass(Aggregate.Created, Aggregate.Event)


This :class:`~eventsourcing.domain.Aggregate` class has three methods, which can be used
by subclasses:

* the "private" class method :func:`~eventsourcing.domain.Aggregate._create`
  will create new aggregate objects;

* the object method :func:`~eventsourcing.domain.Aggregate.trigger_event`
  can be used to trigger subsequent events; and

* the object method :func:`~eventsourcing.domain.Aggregate.collect_events`
  returns new events that have just been triggered.

These methods are explained below, with a :ref:`simple example <Aggregate simple example>`
that shows how it works.


Creating new aggregates
-----------------------

The :class:`~eventsourcing.domain.Aggregate` class has a "private" class method
:func:`~eventsourcing.domain.Aggregate._create`. It is used to create new aggregate
objects. It will usually be called by a "public" class method defined on a subclass
of :class:`~eventsourcing.domain.Aggregate`. See the ``create()`` method of the
``Dog`` class in the :ref:`simple example <Aggregate simple example>` below.

.. code-block:: python

    aggregate = Aggregate._create(Aggregate.Created)


The :func:`~eventsourcing.domain.Aggregate._create` method creates new aggregates in the
following way. It constructs a new "created" event object, the first of a sequence of events
belonging to the aggregate. The "created" event's :func:`~eventsourcing.domain.CanInitAggregate.mutate`
method is used to construct a new aggregate object. The "created" event object is attached to the
new aggregate object, so that the event may be collected and recorded, and later reused to reconstruct
the aggregate in its initial state. The new aggregate object is returned to the caller.

To construct the "created" event object, the :func:`~eventsourcing.domain.Aggregate._create`
method needs an event class, and constructor arguments for the event class. Both the event class
and the constructor arguments can be provided as the method arguments (``event_class``,
``id``, ``**kwargs``).

The ``event_class`` argument of the :func:`~eventsourcing.domain.Aggregate._create` method
is required. It specifies the class of the event object to be constructed. The base
:class:`Aggregate.Created <eventsourcing.domain.Aggregate.Created>` class can be used directly. But more
usually a specific "created" event class is defined for the aggregate, with a suitable
class name and attributes that represent the particular beginning of the aggregate. Such a
"created" event class should be named using a past participle that describes the particular
initiation or beginning of this particular type of aggregate, such as "Started", "Opened",
or indeed "Created". If you are following Domain-Driven Design, this a matter for the
project's ubiquitous language.

The ``id`` argument of the :func:`~eventsourcing.domain.Aggregate._create` is optional.
If a value of the ``id`` argument is provided, it will be used as the "created" event object's
:py:attr:`~eventsourcing.domain.DomainEvent.originator_id`. It is expected to be a Python
:class:`~uuid.UUID` object. If a value is not provided, by default a
`version-4 UUID <https://en.wikipedia.org/wiki/Universally_unique_identifier#Version_4_(random)>`_
will be created by calling the aggregate class method
:func:`~eventsourcing.domain.MetaAggregate.create_id`. The
:func:`~eventsourcing.domain.MetaAggregate.create_id` can be overridden on aggregate classes
to customize the generate of aggregate IDs.
This value will be used to uniquely identify the new aggregate in the domain model.

As we have seen :ref:`above <Domain events>`, the arguments needed when constructing any
domain event are :py:attr:`~eventsourcing.domain.DomainEvent.originator_id`,
:py:attr:`~eventsourcing.domain.DomainEvent.originator_version`, and
:py:attr:`~eventsourcing.domain.DomainEvent.timestamp`.
An :class:`~eventsourcing.domain.AggregateCreated`
object also needs an :py:attr:`~eventsourcing.domain.AggregateCreated.originator_topic`.
By default, the :py:attr:`~eventsourcing.domain.DomainEvent.originator_version` value
will be set to ``1``. The event's :py:attr:`~eventsourcing.domain.AggregateCreated.originator_topic`
value will be derived from the aggregate class itself, using the library's
:func:`~eventsourcing.utils.get_topic` function. The event's
:py:attr:`~eventsourcing.domain.DomainEvent.timestamp` will be generated by calling
:func:`~eventsourcing.domain.DomainEvent.create_timestamp` to create a timezone-aware
Python :class:`~datetime.datetime` object.

"Created" event subclasses may define further attributes that will need to be supplied as
constructor arguments. For this reason, the :func:`~eventsourcing.domain.Aggregate._create`
method also accepts variable keyword arguments ``**kwargs``. They will be used as additional
event constructor arguments. Since the "created" event object will be constructed with these
additional arguments, so these variable keyword arguments must be matched by the particular
attributes of the "created" event class. An error will be raised if the arguments are
mismatched.

After creating the event object, its :func:`~eventsourcing.domain.CanInitAggregate.mutate`
method will be used to construct a new aggregate object. The attributes of the event will
be used by the :func:`~eventsourcing.domain.CanInitAggregate.mutate` method to construct
the aggregate. Therefore, if the "created" event defines any additional event attributes,
beyond the four attributes of :class:`~eventsourcing.domain.AggregateCreated`, then the
aggregate's ``__init__()`` method must accept these additional attributes.

Having constructed the aggregate object from the "created" event object, the
:func:`~eventsourcing.domain.Aggregate._create` method will then return the aggregate
object to the caller. Just before returning the aggregate object, the "created" event
object is appended to a list of "pending" events on the aggregate object, so that the
event object can be collected and recorded, and used in future to reconstruct the
aggregate object.

Aggregate object attributes
---------------------------

Having been created, the new aggregate object has a new ID, which is presented
by its :py:obj:`~eventsourcing.domain.Aggregate.id` property. The ID is a ``UUID``,
either the value passed to the :func:`~eventsourcing.domain.Aggregate._create` method
with the ``id`` argument, or that which is created by the aggregate class's
:func:`~eventsourcing.domain.MetaAggregate.create_id` method.

.. code-block:: python

    from uuid import UUID

    assert isinstance(aggregate.id, UUID)


The aggregate object has a version number. The version number is presented by its
:py:obj:`~eventsourcing.domain.Aggregate.version` property, and is a Python :class:`int`.
The initial version of a newly created aggregate is, by default, always ``1``. If you want
to start at a different number, set ``INITIAL_VERSION`` on the aggregate class.

.. code-block:: python

    assert aggregate.version == 1


The aggregate object has a :py:obj:`~eventsourcing.domain.Aggregate.created_on`
property which gives the date and time when the aggregate object was created. The value
of this property is determined by the :py:attr:`~eventsourcing.domain.DomainEvent.timestamp`
attribute of the "created" event. The timestamps are timezone-aware Python
:class:`~datetime.datetime` objects.

.. code-block:: python

    assert isinstance(aggregate.created_on, datetime)


The aggregate object also has a :py:obj:`~eventsourcing.domain.Aggregate.modified_on`
property, which gives the date and time when the aggregate object was last modified.
It is determined by the timestamp attribute of the last event in the aggregate's sequence.

.. code-block:: python

    assert isinstance(aggregate.modified_on, datetime)


Initially, since there is only one event in the aggregate's sequence,
the :py:obj:`~eventsourcing.domain.Aggregate.created_on` and
:py:obj:`~eventsourcing.domain.Aggregate.modified_on` values are
identical, and equal to the timestamp of the "created" event.

.. code-block:: python

    assert aggregate.created_on == aggregate.modified_on


Triggering subsequent events
----------------------------

An :class:`~eventsourcing.domain.Aggregate` has a method
:func:`~eventsourcing.domain.Aggregate.trigger_event` which can be called
to create a subsequent aggregate event object.

.. code-block:: python

    aggregate.trigger_event(Aggregate.Event)


This method can be called by the command methods of an aggregate to
capture the decisions that it makes. For example, see the
``add_trick()`` method of the ``Dog`` class in the :ref:`example <Aggregate simple example>`
below.

The creation of an event object by a command method is the final stage in the
coming-to-be of a private individual occasion of experience within the aggregate,
a decision making process that begins when the command method is called and ends
with the creation of the event object. The creation of the event object is also the
beginning of the transition of this private individuality to the publicity of many
such things, one stubborn fact amongst the many which contribute determination to
the state of an event-sourced aggregate. The events themselves don't fully determine
the state of the aggregate, since the state of the aggregate is a function of the
events, and the function is another fact that also contributes to determining the
state of the aggregate.

The :func:`~eventsourcing.domain.Aggregate.trigger_event` method has a required
positional argument ``event_class``. The value of this argument determines the type
of event object that will be "triggered". The event class should derive from the
:class:`~eventsourcing.domain.AggregateEvent` discussed :ref:`above <Aggregate events>`,
whilst not being a "created" event. The
:class:`~eventsourcing.domain.Aggregate.Event` class can be used as a base class to
define the subsequent aggregate event classes needed by in your domain model. For example,
see the ``TrickAdded`` class in the :ref:`example <Aggregate simple example>` below.
As mentioned above, aggregate event classes are normally named using past participles.
The class name describes what was decided by the command method, such as "Done", "Updated",
"Closed", names that are meaningful in your domain, expressing and helping to constitute
your project's ubiquitous language.

The :func:`~eventsourcing.domain.Aggregate.trigger_event` method also accepts variable
keyword-only arguments ``**kwargs`` which will also be used to construct the aggregate event
object. As with the :func:`~eventsourcing.domain.Aggregate._create` method described above, the
event object will be constructed with these arguments, and so any extra arguments must
be matched by the attributes of the event class. For example, in the
:ref:`example <Aggregate simple example>` below, the ``add_trick()`` command
calls :func:`~eventsourcing.domain.Aggregate.trigger_event` with a ``trick`` keyword
that matches the ``trick`` attribute on the ``TrickAdded`` event class.

As discussed :ref:`above <Domain events>`, the arguments needed when constructing any
domain event are :py:attr:`~eventsourcing.domain.DomainEvent.originator_id`,
:py:attr:`~eventsourcing.domain.DomainEvent.originator_version`, and
:py:attr:`~eventsourcing.domain.DomainEvent.timestamp`.
The :func:`~eventsourcing.domain.Aggregate.trigger_event` method uses the :py:attr:`~eventsourcing.domain.Aggregate.id` attribute
of the aggregate as the :py:attr:`~eventsourcing.domain.DomainEvent.originator_id` of the new
aggregate event. The :py:attr:`~eventsourcing.domain.DomainEvent.originator_version` of the
new aggregate event is calculated by adding ``1`` to the current aggregate :py:attr:`~eventsourcing.domain.Aggregate.version`.
It calls :func:`~eventsourcing.domain.DomainEvent.create_timestamp` on the event
class to create a timezone-aware Python :class:`~datetime.datetime` object that is
used as the :py:attr:`~eventsourcing.domain.DomainEvent.timestamp` value of the
aggregate event.

After creating the aggregate event object, the :func:`~eventsourcing.domain.Aggregate.trigger_event` method
will "mutate" the aggregate with the event. That is to say, the state of the aggregate will
be changed according to the state of the event. It calls the event object's
:func:`~eventsourcing.domain.CanMutateAggregate.mutate` method, which calls
the event's :func:`~eventsourcing.domain.CanMutateAggregate.apply` method
and then assigns new values to the aggregate's :py:attr:`~eventsourcing.domain.Aggregate.version` and :py:attr:`~eventsourcing.domain.Aggregate.modified_on`
attributes. Please note, it's possible to code "immutable" aggregates, but things
need to be arranged slightly differently (see the :ref:`example aggregates <Example aggregates>`
for some suggestions).

Finally, :func:`~eventsourcing.domain.Aggregate.trigger_event` method will append the
new aggregate event to the aggregate object's list of pending events.

Hence, after calling :func:`~eventsourcing.domain.Aggregate.trigger_event`, the aggregate's
:py:obj:`~eventsourcing.domain.Aggregate.version` will have been incremented by ``1``, and the
:py:attr:`~eventsourcing.domain.Aggregate.modified_on` time should be greater than the :py:attr:`~eventsourcing.domain.Aggregate.created_on` time.

.. code-block:: python

    assert aggregate.version == 2
    assert aggregate.modified_on > aggregate.created_on


Collecting pending events
-------------------------

The :class:`~eventsourcing.domain.Aggregate` class has a "public" object method
:func:`~eventsourcing.domain.Aggregate.collect_events` which can be called to
collect new aggregate event objects. New aggregate event objects are appended
to the aggregate's list of pending events when a new aggregate is "created"
and when subsequent events are triggered.

Hence, the example ``aggregate`` so far has two pending events.

.. code-block:: python

    assert len(aggregate.pending_events) == 2

    pending_events = aggregate.collect_events()

    assert len(pending_events) == 2
    assert len(aggregate.pending_events) == 0

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

This method will drain the aggregate object's list of pending events, so that if this
method is called again before any further aggregate events have been appended, it will
return an empty list.

.. code-block:: python

    pending_events = aggregate.collect_events()
    assert len(pending_events) == 0


.. _Aggregate simple example:

Simple example
--------------

In the example below, the ``Dog`` aggregate is defined as a subclass of the :class:`~eventsourcing.domain.Aggregate` class.

.. code-block:: python

    class Dog(Aggregate):
        def __init__(self):
            self.tricks = []

        @classmethod
        def create(cls):
            return cls._create(cls.Created, id=uuid4())

        class Created(Aggregate.Created):
            pass

        def add_trick(self, trick):
            self.trigger_event(self.TrickAdded, trick=trick)

        class TrickAdded(Aggregate.Event):
            trick: str

            def apply(self, dog):
                dog.tricks.append(self.trick)


The ``__init__()`` method
initialises a ``tricks`` attribute with an empty Python ``list`` object.

The ``Dog.create()`` class method creates and returns
a new ``Dog`` aggregate object. It calls the inherited
:func:`~eventsourcing.domain.Aggregate._create` method that
we discussed above. It uses its own ``Created`` event class as
the value of the ``event_class`` argument. It uses a
`version-4 UUID <https://en.wikipedia.org/wiki/Universally_unique_identifier#Version_4_(random)>`_
object as the value of the ``id`` argument. See the :ref:`Namespaced IDs <Namespaced IDs>`
section below for a discussion about using version-5 UUIDs.

The ``add_trick()`` method is a command method that triggers
a ``Dog.TrickAdded`` domain event. It calls the inherited
:func:`~eventsourcing.domain.Aggregate.trigger_event` method.
The event is triggered with the method argument ``trick``.

The nested ``TrickAdded`` class is a frozen data class that extends the
base aggregate event class :class:`~eventsourcing.domain.Aggregate.Event`
(also a frozen data class) with a field ``trick`` which is defined as a
Python :class:`str`. An ``apply()`` method is defined which appends the
``trick`` value to the aggregate's ``tricks``. This method is called when
the event is triggered (see :ref:`Aggregate events <Aggregate events>`).

By defining the event class under the command method which triggers it, and then
defining an ``apply()`` method as part of the event class definition, the story of
calling a command method, triggering an event, and evolving the state of the aggregate
is expressed in three cohesive parts that are neatly co-located.

Having defined the ``Dog`` aggregate class, we can create a new ``Dog``
aggregate object by calling the ``Dog.create()`` class method.

.. code-block:: python

    dog = Dog.create()
    assert isinstance(dog, Dog)

The aggregate's attributes :py:attr:`~eventsourcing.domain.Aggregate.created_on` and :py:attr:`~eventsourcing.domain.Aggregate.modified_on` show
when the aggregate was created and when it was modified. Since there
has only been one domain event, these are initially equal.
These values follow from the :py:attr:`~eventsourcing.domain.DomainEvent.timestamp` values of the domain event
objects, and represent when the aggregate's first and last domain events
were created.

.. code-block:: python

    assert dog.created_on == dog.modified_on


We can now call the aggregate object methods. The ``Dog`` aggregate has a command
method ``add_trick()`` which triggers the ``TrickAdded`` event. The
``apply()`` method of the ``TrickAdded`` class appends the ``trick``
of the event to the ``tricks`` of the ``dog``. So when we call the ``add_trick()``
command, the argument ``trick`` will be appended to the ``tricks``.

.. code-block:: python

    # Commands methods trigger events.
    dog.add_trick("roll over")
    dog.add_trick("fetch ball")
    dog.add_trick("play dead")

    # State of aggregate object has changed.
    assert dog.tricks[0] == "roll over"
    assert dog.tricks[1] == "fetch ball"
    assert dog.tricks[2] == "play dead"


Now that more than one domain event has been created, the aggregate's
:py:attr:`~eventsourcing.domain.Aggregate.modified_on` value is greater than its
:py:attr:`~eventsourcing.domain.Aggregate.created_on` value.

.. code-block:: python

    assert dog.modified_on > dog.created_on


The resulting domain events are now held internally in the aggregate in
a list of pending events. The pending events can be collected by calling
the aggregate's :func:`~eventsourcing.domain.Aggregate.collect_events` method.
These events are pending to be saved, and indeed the library's
:ref:`application <Application objects>` object has a
:func:`~eventsourcing.application.Application.save` method which
works by calling this method. So far, we have created four domain events and
we have not yet collected them, and so there will be four pending events: one
``Created`` event, and three ``TrickAdded`` events.

.. code-block:: python

    # Has four pending events.
    assert len(dog.pending_events) == 4

    # Collect pending events.
    pending_events = dog.collect_events()
    assert len(pending_events) == 4
    assert len(dog.pending_events) == 0

    assert isinstance(pending_events[0], Dog.Created)
    assert isinstance(pending_events[1], Dog.TrickAdded)
    assert isinstance(pending_events[2], Dog.TrickAdded)
    assert isinstance(pending_events[3], Dog.TrickAdded)
    assert pending_events[1].trick == "roll over"
    assert pending_events[2].trick == "fetch ball"
    assert pending_events[3].trick == "play dead"

    assert pending_events[0].timestamp == dog.created_on
    assert pending_events[3].timestamp == dog.modified_on


As discussed above, the event objects can be used to reconstruct
the current state of the aggregate, by calling their
:func:`~eventsourcing.domain.CanMutateAggregate.mutate` methods.

.. code-block:: python

    copy = None
    for domain_event in pending_events:
        copy = domain_event.mutate(copy)

    assert isinstance(copy, Dog)
    assert copy.id == dog.id
    assert copy.version == dog.version
    assert copy.created_on == dog.created_on
    assert copy.modified_on == dog.modified_on
    assert copy.tricks == dog.tricks


The :func:`~eventsourcing.application.Repository.get`
method of the :ref:`application repository <Repository>` class
works by calling these methods in this way for this purpose.


.. _Namespaced IDs:

Namespaced IDs
--------------

Aggregates can be created with `version-5 UUIDs <https://en.wikipedia
.org/wiki/Universally_unique_identifier#Versions_3_and_5_(namespace_name-based)>`_
so that their IDs can be generated from a given name in a namespace. They can
be used for example to create IDs for aggregates with fixed names that you want
to identify by name. For example, you can use this technique to identify a system
configuration object. This technique can also be used to identify index aggregates
that hold the IDs of aggregates with mutable names, or used to index other mutable
attributes of an event-sourced aggregate. It isn't possible to change the ID of an
existing aggregate, because the domain events will need to be stored together in a
single sequence. And so, using an index aggregate that has an ID that can be recreated
from a particular value of a mutable attribute of another aggregate to hold the
ID of that aggregate with makes it possible to identify that aggregate from that
particular value. Such index aggregates can be updated when the mutable
attribute changes, or not.

For example, if you have a collection of page aggregates with names that might change,
and you want to be able to identify the pages by name, then you can create index
aggregates with version-5 UUIDs that are generated from the names, and put the IDs
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

.. code-block:: python

    from uuid import NAMESPACE_URL, uuid5
    from typing import Optional

    from eventsourcing.domain import Aggregate


    class Page(Aggregate):
        def __init__(self, name: str, body: str):
            self.name = name
            self.body = body

        @classmethod
        def create(cls, name: str, body: str = ""):
            return cls._create(
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

            def apply(self, page):
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

            def apply(self, index):
                index.ref = self.ref


We can use the classes above to create a "page" aggregate with a name that
we will then change. We can at the same time create an index object for the
page.

.. code-block:: python

    page = Page.create(name="Erth")
    index1 = Index.create(page.name, page.id)


Let's imagine these two aggregate are saved together, and having
been saved can be retrieved by ID. See the discussion about
:ref:`saving multiple aggregates <Saving multiple aggregates>`
to see how this works in an application object.

We can use the page name to recreate the index ID, and use the index
ID to retrieve the index aggregate. We can then obtain the page ID from
the index aggregate, and then use the page ID to get the page aggregate.

.. code-block:: python

    index_id = Index.create_id("Erth")
    assert index_id == index1.id
    assert index1.ref == page.id


Now let's imagine we want to correct the name of the page. We
can update the name of the page, and create another index aggregate
for the new name, so that later we can retrieve the page using
its new name.

.. code-block:: python

    page.update_name("Earth")
    index2 = Index.create(page.name, page.id)

We can drop the reference from the old index, so that it can
be used to refer to a different page.

.. code: python

    index.1.update_ref(None)

We can now use the new name to get the ID of the second index aggregate,
and imagine using the second index aggregate to get the ID of the page.

.. code-block:: python

    index_id = Index.create_id("Earth")
    assert index_id == index2.id
    assert index2.ref == page.id


This technique of using names to discover aggregates is demonstrated further
in the discussion about :ref:`saving multiple aggregates <Saving multiple aggregates>`
in the application module documentation.

Alternative styles for implementing aggregate projector
-------------------------------------------------------

The advantage of defining :func:`~eventsourcing.domain.CanMutateAggregate.apply`
methods on the aggregate event classes is that the aggregate projector is implemented
in a way that keeps the code that mutates the aggregate state close to the code that
defines the event class.

However, there are two important disadvantages that come with using
:func:`~eventsourcing.domain.CanMutateAggregate.apply`
methods on the aggregate event classes to define the aggregate projector function.
Firstly, the aggregate that is to be mutated is an argument to the event's
method. There is a "reverse intuition" that comes with mutating method arguments.
It is more natural to set values on ``self`` using the values given by method
arguments, than to set values on the method argument using values taken from
``self``. Secondly, it is perhaps illegitimate for the event to use "private"
attributes of the aggregate, but then if we code for mutating the state of the
aggregate with "public" methods we extend the "public interface" of the aggregate
beyond the event-triggering command methods which genuine clients of the aggregate
should be using.

An alternative to defining :func:`~eventsourcing.domain.CanMutateAggregate.apply` methods
on all the aggregate event classes is to define the aggregate mutator function on
on the aggregate class.

For example, a base ``Event`` class can be defined to have an :func:`~eventsourcing.domain.CanMutateAggregate.apply`
method which calls a ``when()`` method on the aggregate object, passing the aggregate
event object as an argument. The aggregate's ``when()`` method can be decorated with the
``@singledispatchmethod`` decorator, allowing event-specific parts to be registered.
Event-specific parts of the projection can then be defined that will apply a particular
type of event to the aggregate in a particular way. Defining the aggregate projector
with methods on the aggregate class has the advantage of setting values on ``self``,
which avoids the reverse of intuition that occurs when writing :func:`~eventsourcing.domain.CanMutateAggregate.apply` methods
on the events, and makes it legitimate to set values on "private" attributes of the
aggregate. These event-specific functions can be coded directly underneath the event
that is triggered, keeping the command-event-mutator codes close together. See the
``Cargo`` aggregate in the domain model section of the
:ref:`Cargo shipping example <Cargo shipping example>`
for an example of this style of implementing aggregate projector functions.


..
    #include-when-testing
..
    from eventsourcing.examples.cargoshipping.domainmodel import Location, singledispatchmethod

.. code-block:: python

    class Cargo(Aggregate):

        ...

        class Event(Aggregate.Event):
            def apply(self, aggregate) -> None:
                aggregate.when(self)

        @singledispatchmethod
        def when(self, event) -> None:
            """
            Default method to apply an aggregate event to the aggregate object.
            """

        def change_destination(self, destination: Location) -> None:
            self.trigger_event(
                self.DestinationChanged,
                destination=destination,
            )

        class DestinationChanged(Event):
            destination: Location

        @when.register
        def destination_changed(self, event: DestinationChanged) -> None:
            self._destination = event.destination



A further, perhaps more "purist", alternative is to use a mutator function defined at
the module level. But then the event-specific parts of the aggregate projector will
become more distant from the definition of the event. And in this case, again, we face
an uncomfortable choice between either setting "private" attributes on the aggregate or
extending the "public" interface beyond that which clients should be using. A more extreme
version of this style could avoid even the event's :func:`~eventsourcing.domain.CanMutateAggregate.mutate` method being called, by
taking responsibility for everything that is performed by the event's :func:`~eventsourcing.domain.CanMutateAggregate.mutate` methods.
But then any common aspects which are nicely factored by the :func:`~eventsourcing.domain.CanMutateAggregate.mutate` methods may need
to be repeated on each part of the projection that handles a particular type of event.
However, this more extreme style is supported by the library. A function can be
passed into the :func:`~eventsourcing.application.Repository.get` method of an
:ref:`application repository <Repository>` using the ``projector_func`` argument
of that method, and then it will be called successively with each aggregate event
in the sequence of recorded events, so that the aggregate events can be projected
into the aggregate state in whichever way is desired.

But there is another issue that all of the approaches above suffer from. That is repetition
in the specification and use of the event attributes. They appear in the command method as
either command method arguments or as local variables. They appear in the triggering of the
event object. They appear in the definition of the event. And they appear when mutating
the state of the aggregate. This style makes everything very explicit, which is good. But it
also makes the expression of these concerns rather verbose, relative to what is actually
possible.

The library offers a more concise style for expressing these concerns. The :ref:`declarative syntax <Declarative syntax>`,
especially the :func:`@event<eventsourcing.domain.event>` decorator, which you may have seen on the project's README page and the
`Introduction <introduction.html>`_ and the :doc:`Tutorial </topics/tutorial>`, is explained in detail below.
This offers a more concise style which avoids all of the actually unnecessary repetition, keeps the
specification of the event even closer to the code that mutates the aggregate, and allows the aggregate
to be mutated in a natural way using "private" attributes.

Of course, the possibilities for coding mutator functions are endless. And you should
choose whichever style you prefer.


.. _Declarative syntax:

Declarative syntax
==================

You may have noticed a certain amount of repetition in the definitions of the
aggregates above. In several places, the same argument was defined in a command
method, on an event class, and in an apply method. The library offers a more concise
way to express aggregates by using a declarative syntax. This is possibly the most
concise way of expressing an event-sourced domain model across all programming
languages. It is the style that is used in the :doc:`Introduction </topics/introduction>`
and in the :doc:`Tutorial </topics/tutorial>`.


Create new aggregate by calling the aggregate class directly
------------------------------------------------------------

An aggregate can be "created" by calling the aggregate class
directly. You don't actually need to define a class method to do this, although
you may wish to express your project's ubiquitous language by doing so.

.. code-block:: python

    class MyAggregate(Aggregate):
        class Started(Aggregate.Created):
            pass


    # Call the class directly.
    agg = MyAggregate()

    # There is one pending event.
    pending_events = agg.collect_events()
    assert len(pending_events) == 1
    assert isinstance(pending_events[0], MyAggregate.Started)

    # The pending event can be used to reconstruct the aggregate.
    copy = pending_events[0].mutate(None)
    assert copy.id == agg.id
    assert copy.created_on == agg.created_on


Using the init method to define the created event class
-------------------------------------------------------

If a "created" event class is not defined on an aggregate class,
one will be automatically defined. The attributes of this event
class will be derived by inspecting the signature of the
``__init__()`` method. The example below has an init method that
has a ``name`` argument. Because this example doesn't have a "created"
event class defined explicitly on the aggregate class, a "created"
event class will be defined automatically to match the signature
of the init method. That is, a "created" event class will be defined
that has an attribute ``name``.

..
    #include-when-testing
..
    import eventsourcing.utils
    eventsourcing.utils._topic_cache.clear()

.. code-block:: python

    class MyAggregate(Aggregate):
        def __init__(self, name):
            self.name = name


    # Call the class with a 'name' argument.
    agg = MyAggregate(name="foo")
    assert agg.name == "foo"

    # There is one pending event.
    pending_events = agg.collect_events()
    assert len(pending_events) == 1

    # The pending event is a "created" event.
    assert isinstance(pending_events[0], MyAggregate.Created)

    # The "created" event is defined on the aggregate class.
    assert type(pending_events[0]).__qualname__ == "MyAggregate.Created"

    # The "created" event has a 'name' attribute.
    pending_events[0].name == "foo"

    # The "created" event can be used to reconstruct the aggregate.
    copy = pending_events[0].mutate(None)
    assert copy.name == agg.name


Please note, by default the name "Created" will be used for an automatically
defined "created" event class. However, the name of the "created" class can be specified
using the aggregate class argument ``created_event_name``, and it can be defined by using
an :func:`@event<eventsourcing.domain.event>` decorator on the aggregate's ``__init__()`` method.


Dataclass-style init methods
----------------------------

Python's data class annotations can be used to define an aggregate's
``__init__()`` method. A "created" event class will then be
automatically defined from the automatically defined method.

..
    #include-when-testing
..
    eventsourcing.utils._topic_cache.clear()

.. code-block:: python

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


Anything that works on a data class should work here too.
For example, optional arguments can be defined by providing
default values on the attribute definitions.

..
    #include-when-testing
..
    eventsourcing.utils._topic_cache.clear()

.. code-block:: python

    @dataclass
    class MyAggregate(Aggregate):
        name: str = "bar"


    # Call the class without a name.
    agg = MyAggregate()
    assert agg.name == "bar"

    # Call the class with a name.
    agg = MyAggregate("foo")
    assert agg.name == "foo"


And you can define "non-init argument" attributes, attributes
that will be initialised in the ``__init__()`` method but not
appear as arguments of that method, by using the ``field``
feature of the dataclasses module.

..
    #include-when-testing
..
    eventsourcing.utils._topic_cache.clear()

.. code-block:: python

    from dataclasses import field
    from typing import List

    @dataclass
    class MyAggregate(Aggregate):
        tricks: List[str] = field(default_factory=list, init=False)


    # Create a new aggregate.
    agg = MyAggregate()

    # The aggregate has a list.
    assert agg.tricks == []


Please note, when using the dataclass-style for defining ``__init__()``
methods, using the :data:`@dataclass` decorator on your aggregate class
will inform your IDE of the method signature, and then command completion
should work when calling the class. The annotations will in any case be used
to create an ``__init__()`` method when the class does not already have an
``__init__()``. Using the dataclass decorator merely enables code completion
and syntax checking, but the code will run just the same with or without the
:data:`@dataclass` decorator being applied to aggregate classes that
are defined using this style.


Declaring the created event class name
--------------------------------------

To give the "created" event class a particular name, use the class argument ``created_event_name``.

..
    #include-when-testing
..
    eventsourcing.utils._topic_cache.clear()

.. code-block:: python

    class MyAggregate(Aggregate, created_event_name="Started"):
        name: str

    # Create a new aggregate.
    agg = MyAggregate("foo")

    # The created event class is called "Started".
    pending_events = agg.collect_events()
    assert isinstance(pending_events[0], MyAggregate.Started)


This is equivalent to declaring a "created" event class
on the aggregate class.

..
    #include-when-testing
..
    eventsourcing.utils._topic_cache.clear()

.. code-block:: python

    class MyAggregate(Aggregate):
        class Started(Aggregate.Created):
            pass

    # Create a new aggregate.
    agg = MyAggregate()

    # The created event class is called "Started".
    pending_events = agg.collect_events()
    assert isinstance(pending_events[0], MyAggregate.Started)


If more than one "created" event class is defined on the aggregate class, perhaps
because the name of the "created" event class was changed and there are stored events
that were created using the old "created" event class that need to be supported,
then ``created_event_name`` can be used to identify which "created" event
class is the one to use when creating new aggregate instances.

..
    #include-when-testing
..
    eventsourcing.utils._topic_cache.clear()

.. code-block:: python

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


If ``created_event_name`` is used but the value does not match
the name of any of the "created" event classes that are explicitly defined on the
aggregate class, then an event class will be automatically defined, and it
will be used when creating new aggregate instances.

..
    #include-when-testing
..
    eventsourcing.utils._topic_cache.clear()

.. code-block:: python

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

By default, the aggregate ID will be a version-4 UUID, automatically
generated when a new aggregate is created. However, the aggregate ID
can also be defined as a function of the arguments used to create the
aggregate. You can do this by defining a ``create_id()`` method.

..
    #include-when-testing
..
    eventsourcing.utils._topic_cache.clear()

.. code-block:: python

    class MyAggregate(Aggregate):
        name: str

        @staticmethod
        def create_id(name: str):
            return uuid5(NAMESPACE_URL, f"/my_aggregates/{name}")


    # Create a new aggregate.
    agg = MyAggregate(name="foo")
    assert agg.name == "foo"

    # The aggregate ID is a version-5 UUID.
    assert agg.id == MyAggregate.create_id("foo")


If a ``create_id()`` method is defined on the aggregate class, the base class
method :func:`~eventsourcing.domain.MetaAggregate.create_id`
will be overridden. The arguments used in this method must be a subset of the
arguments used to create the aggregate. The base class method simply returns a
version-4 UUID, which is the default behaviour for generating aggregate IDs.

Alternatively, an ``id`` attribute can be declared on the aggregate
class, and an ``id`` argument supplied when creating new aggregates.

..
    #include-when-testing
..
    eventsourcing.utils._topic_cache.clear()

.. code-block:: python

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
because :py:attr:`~eventsourcing.domain.Aggregate.id` is defined as a read-only
property on the base aggregate class.

..
    #include-when-testing
..
    eventsourcing.utils._topic_cache.clear()

.. code-block:: python

    class MyAggregate(Aggregate):
        def __init__(self, id: UUID):
            self._id = id


    # Create an aggregate with the ID.
    agg = MyAggregate(id=agg_id)
    assert agg.id == agg_id



The event decorator
--------------------

A more concise way of expressing the concerns around defining, triggering and
applying subsequent aggregate events can be achieved by using the library's
:func:`@event<eventsourcing.domain.event>` decorator on aggregate
command methods.

When decorating a method with the :func:`@event<eventsourcing.domain.event>`
decorator, the method signature will be used to automatically define an aggregate
event class. And when the method is called, the event will firstly be triggered
with the values given when calling the method, so that an event is created and
used to mutate the state of the aggregate. The body of the decorated method
will be used as the :func:`~eventsourcing.domain.CanMutateAggregate.apply`
method of the event, both after the event has been triggered and when the
aggregate is reconstructed from stored events. The name of the event class
can be passed to the decorator as a Python ``str``.

..
    #include-when-testing
..
    eventsourcing.utils._topic_cache.clear()

.. code-block:: python

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

Please also note, if an exception happens to be raised in the decorated method
body, then the triggered event will not be appended to the internal list of
pending events as described above. If you are careful, this behaviour (of not
appending the event to the list of pending events) can be used to validate
the state of the event against the current state of the aggregate. But if
you wish to continue using the same aggregate instance after catching a
validation exception in the caller of the decorated method, please just be
careful to complete all validation before adjusting the state of the aggregate,
otherwise you will need to retrieve a fresh instance from the repository.

This decorator also works with the ``__init__()`` methods.

..
    #include-when-testing
..
    eventsourcing.utils._topic_cache.clear()

.. code-block:: python

    class MyAggregate(Aggregate):
        @event("Started")
        def __init__(self, name):
            self.name = name


    # Call the class with a 'name' argument.
    agg = MyAggregate(name="foo")
    assert agg.name == "foo"

    # There is one pending event.
    pending_events = agg.collect_events()
    assert len(pending_events) == 1

    # The pending event is a "created" event.
    assert isinstance(pending_events[0], MyAggregate.Started)

    # The "created" event is defined on the aggregate class.
    assert type(pending_events[0]).__qualname__ == "MyAggregate.Started"

    # The "created" event has a 'name' attribute.
    pending_events[0].name == "foo"

    # The "created" event can be used to reconstruct the aggregate.
    copy = pending_events[0].mutate(None)
    assert copy.name == agg.name


Inferring the event class name from the method name
---------------------------------------------------

The :func:`@event<eventsourcing.domain.event>` decorator can be used without providing
the name of an event. If the decorator is used without any
arguments, the name of the event will be derived from the
method name. The method name is assumed to be lower case
and underscore-separated. The name of the event class is
constructed by firstly splitting the name of the method by its
underscore characters, then by capitalising the resulting parts,
and then by concatenating the capitalised parts to give an
"upper camel case" class name. For example, a method name
``name_updated`` would give an event class name ``NameUpdated``.

..
    #include-when-testing
..
    eventsourcing.utils._topic_cache.clear()

.. code-block:: python

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

..
    #include-when-testing
..
    eventsourcing.utils._topic_cache.clear()

.. code-block:: python

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
instead of the :func:`@event<eventsourcing.domain.event>` decorator (it does the same thing).

..
    #include-when-testing
..
    eventsourcing.utils._topic_cache.clear()

.. code-block:: python

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


The Dog aggregate class revisited
-----------------------------------

Using the declarative syntax described above, the ``Dog`` aggregate in
the :ref:`Simple example <Aggregate simple example>` above can be
expressed more concisely in the following way.

.. code-block:: python

    class Dog(Aggregate):
        def __init__(self):
            self.tricks = []

        @event("TrickAdded")
        def add_trick(self, trick):
            self.tricks.append(trick)


In this example, the ``Dog.TrickAdded`` event is automatically
defined by inspecting the ``add_trick()`` method. The event class
name "TrickAdded" is given to the method's decorator. The
body of the ``add_trick()`` method will be used as the ``apply()``
method of the ``Dog.TrickAdded`` event.

The ``Dog`` aggregate class can be called directly. Calling the
``add_trick()`` method will trigger a ``Dog.TrickAdded``
event, and this event will be used to mutate the state of the aggregate,
such that the ``add_trick()`` method argument ``trick`` will be
appended to the aggregate's ``tricks`` attribute.

.. code-block:: python

    dog = Dog()
    dog.add_trick("roll over")
    dog.add_trick("fetch ball")
    dog.add_trick("play dead")

    assert dog.tricks[0] == "roll over"
    assert dog.tricks[1] == "fetch ball"
    assert dog.tricks[2] == "play dead"


As before, the pending events can be collected
and used to reconstruct the aggregate object.

.. code-block:: python

    pending_events = dog.collect_events()

    assert len(pending_events) == 4

    copy = reconstruct_aggregate_from_events(pending_events)

    assert copy.id == dog.id
    assert copy.version == dog.version
    assert copy.created_on == dog.created_on
    assert copy.modified_on == dog.modified_on

    assert copy.tricks[0] == "roll over"
    assert copy.tricks[1] == "fetch ball"
    assert copy.tricks[2] == "play dead"


The Page and Index aggregates revisited
---------------------------------------

The ``Page`` and ``Index`` aggregates defined in the above
:ref:`discussion about namespaced IDs <Namespaced IDs>` can be expressed more
concisely in the following way.

.. code-block:: python

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


.. _non-trivial-command-methods:

Non-trivial command methods
---------------------------

In the examples above, the command methods are "trivial", in that the arguments
of the command methods are the same as the attributes of the aggregate events
that they trigger. But often a command method needs to do some work before
triggering an event. In some cases, the command method involves conditional logic,
such that an event might not be triggered. In other cases, the logic of the
command method may be such that different events could be triggered.

The event attributes might be different from the command arguments. For example,
if the triggered event is to have a new date-time value, or a new random UUID, then
the new value must be generated before the event is triggered, not when the event
is applied to the aggregate. Otherwise, a new value will be generated each time the
aggregate is reconstructed, rather than the value being fixed in the stored state
of the aggregate.

Any processing of the command method arguments should be done only once, and not repeated
when reconstructing aggregates from stored events, before the event is triggered. This can
be accomplished with the declarative syntax by defining a "public" method that is not
decorated, which calls a "private" method that is decorated. The "public" command method
will not trigger an event when it is called, and its method body will be executed only when
the command is executed. The "private" method will trigger an event when it is called, and its
method body will be executed each time the event is applied to the aggregate.

To illustrate this, let's consider a command method that has some conditional logic. The
following ``Order`` class is an ordinary Python class. The ``confirm()``  method
simply assigns the given value of its argument ``at`` to the order's ``confirmed_at``
attribute. This method is "trivial", in that the argument of the ``confirm()`` method
is assigned directly to the object attribute. However, the ``pickup()`` method
has some conditional logic. It firstly checks that the order has been confirmed. If
the order as not been confirmed, it raises an exception. Otherwise, if the order has
been confirmed, it calls the "private" ``_pickup()`` method. The "private" ``_pickup()``
method directly assigns the given value of the ``at`` argument to the order's ``pickedup_at``
attribute. The ``pickup()`` method is "non-trivial", in that it has conditional logic which
will only decide to assign the given value of the ``at`` argument to the order object if the
order has been confirmed.

.. code-block:: python

    class Order:
        def __init__(self, name):
            self.name = name
            self.confirmed_at = None
            self.pickedup_at = None

        def confirm(self, at):
            self.confirmed_at = at

        def pickup(self, at):
            if self.confirmed_at is None:
                raise AssertionError("Order is not confirmed")
            self._pickup(at)

        def _pickup(self, at):
            self.pickedup_at = at


We can construct a new instance of the ``Order`` class, and call its
command methods. Calling ``pickup()`` before ``confirm()`` causes
an exception to be raised.

.. code-block:: python

    # Create a new order.
    order = Order("my order")
    assert order.name == "my order"
    assert order.confirmed_at is None
    assert order.pickedup_at is None

    # Can't pickup() before confirm().
    try:
        order.pickup(datetime.now())
    except AssertionError as e:
        assert e.args[0] == "Order is not confirmed"
        assert order.confirmed_at is None
        assert order.pickedup_at is None
    else:
        raise Exception("shouldn't get here")

    # Confirm the order.
    order.confirm(datetime.now())
    assert order.confirmed_at is not None
    assert order.pickedup_at is None

    # Pick up the order.
    from time import sleep
    sleep(0.001)
    order.pickup(datetime.now())
    assert order.confirmed_at is not None
    assert order.pickedup_at is not None
    assert order.pickedup_at > order.confirmed_at


This ordinary Python class can be easily converted into an event-sourced aggregate
by inheriting from :class:`~eventsourcing.domain.Aggregate` and using the
:func:`@event<eventsourcing.domain.event>` decorator on the ``confirm()`` and ``_pickup()`` methods.

.. code-block:: python

    class Order(Aggregate):
        def __init__(self, name):
            self.name = name
            self.confirmed_at = None
            self.pickedup_at = None

        @event("Confirmed")
        def confirm(self, at):
            self.confirmed_at = at

        def pickup(self, at):
            if self.confirmed_at is None:
                raise AssertionError("Order is not confirmed")
            self._pickup(at)

        @event("PickedUp")
        def _pickup(self, at):
            self.pickedup_at = at

Now, when the ``confirm()`` method is called, an ``Order.Confirmed`` event
will be triggered. However, when the ``pickup()`` method is called, an ``Order.PickedUp``
event will be triggered only if the order has been confirmed. The body of the ``pickup()``
method is executed only when the command method is called, and before an event is triggered.
The body of the ``_pickup()`` method is executed after the event is triggered and each
time the event is applied to evolve the state of the aggregate.

We can use the event-sourced ``Order`` aggregate in exactly the same way as
the ordinary Python ``Order`` class.

.. code-block:: python

    # Start a new order, confirm, and pick up.
    order = Order("my order")
    assert order.name == "my order"
    assert order.confirmed_at is None
    assert order.pickedup_at is None

    # Error when calling pickup() before calling confirm().
    try:
        order.pickup(datetime.now())
    except AssertionError as e:
        assert e.args[0] == "Order is not confirmed"
        assert order.confirmed_at is None
        assert order.pickedup_at is None
    else:
        raise Exception("shouldn't get here")

    # Confirm the order.
    order.confirm(datetime.now())
    assert order.confirmed_at is not None
    assert order.pickedup_at is None

    # Pick up the order.
    order.pickup(datetime.now())
    assert order.confirmed_at is not None
    assert order.pickedup_at is not None
    assert order.pickedup_at > order.confirmed_at

The difference is the event-sourced version of the ``Order`` class will
trigger a sequence of aggregate events that can be persisted in a database
and used in future to reconstruct the current state of the order.

.. code-block:: python

    # Collect the aggregate events.
    events = order.collect_events()

    reconstructed = None
    for e in events:
        reconstructed = e.mutate(reconstructed)

    assert reconstructed.name == order.name
    assert reconstructed.confirmed_at == order.confirmed_at
    assert reconstructed.pickedup_at == order.pickedup_at

    assert reconstructed.id == order.id
    assert reconstructed.version == order.version
    assert reconstructed.created_on == order.created_on
    assert reconstructed.modified_on == order.modified_on


Raising exceptions in the body of decorated methods
---------------------------------------------------

It is sometimes possible to decorate a non-trivial command method with
the :func:`@event<eventsourcing.domain.event>` decorator. By raising an exception in the body of a
decorated method, the triggered event will not in fact be appended
to the aggregate's list of pending events, and it will be as if it never
happened. It is important to avoid changing the state of the aggregate instance
before raising an exception, in case the aggregate instance will continue to be
used. It is also important to remember that if the body of a decorated method
has conditional logic, this conditional logic will be executed each time the
aggregate is reconstructed from stored events. Of course, this conditional
logic may be usefully considered as validation of the projection of earlier
events, for example checking the the ``Confirmed`` event is working properly.

If you wish to use this style, just make sure to raise an exception rather
than returning early, and make sure not to change the state of the aggregate
if an exception may be raised later in the method body. Returning early will
mean the event will be appended to the list of pending events. Changing the
state before raising an exception will mean the state of the aggregate instance
will differ from the recorded state. So if your method does change state and
then raise an exception, make sure to obtain a fresh version of the aggregate
before continuing to trigger events in your application.

.. code-block:: python

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
            if self.confirmed_at is None:
                raise AssertionError("Order is not confirmed")
            self.pickedup_at = at

        # Creating the aggregate causes one pending event.
        order = Order("name")
        assert len(order.pending_events) == 1

        # Call pickup() too early raises an exception.
        try:
            order.pickup(datetime.now())
        except AssertionError as e:
            assert e.args[0] == "Order is not confirmed"
        else:
            raise Exception("Shouldn't get here")

        # There is still only one pending event.
        assert len(order.pending_events) == 1

        # The state of the aggregate instance is unchanged.
        assert order.confirmed_at is None
        assert order.pickedup_at is None


Recording command arguments and reprocessing them each time the aggregate is
reconstructed is known as "command sourcing". However, this is still
"event sourcing". Command sourcing is a special case of event sourcing
when the command arguments are used directly, and when the command method
body is executed each time the aggregate is reconstructed from its events.
As mentioned above, command sourcing doesn't work when the command method
body generates new values that aren't a deterministic function of the command
argument. Command sourcing can work if the change of state of the aggregate
is a deterministic function of the command method arguments. However, in most
cases it is more desirable to trigger an event with the results of the work
of the command method, rather than repeating this work each time. The choice
is yours.

In the cases where an aggregate event is to be triggered that has attributes
that are different from the command method arguments, it is necessary, when
using the :func:`@event<eventsourcing.domain.event>` decorator to define and trigger events, to define two
methods with different signatures: a "public" command method that is not
decorated; and a "private" helper method that is decorated. Arguably, this
second method may be well-named by using a past participle rather than the
imperative form.

The :data:`@aggregate` decorator
--------------------------------

Just for fun, the library's :func:`~eventsourcing.domain.aggregate` function can be
used to declare event-sourced aggregate classes. This is equivalent to inheriting
from the library's :class:`~eventsourcing.domain.Aggregate` class. The created
event name can be defined using the ``created_event_name`` argument of the decorator.
However, it is recommended to inherit from the :class:`~eventsourcing.domain.Aggregate`
class rather than using the ``@aggregate`` decorator so that full the
:class:`~eventsourcing.domain.Aggregate` class definition will be visible to your IDE.

..
    #include-when-testing
..
    eventsourcing.utils._topic_cache.clear()

.. code-block:: python

    from eventsourcing.domain import aggregate


    @aggregate(created_event_name="Started")
    class Order:
        def __init__(self, name):
            self.name = name


    order = Order("my order")
    pending_events = order.collect_events()
    assert isinstance(pending_events[0], Order.Started)


Timestamp timezones
===================

The timestamp values mentioned above are timezone-aware Python :class:`datetime`
objects, created when :func:`eventsourcing.domain.DomainEvent.create_timestamp` calls
:func:`datetime.now`. By default, the timezone is set to UTC, as defined by :data:`timezone.utc`
in Python's :data:`datetime` module. It is generally recommended to store date-times as
timezone-aware values with UTC as the timezone, and then localize the values in the
interface to the application, according to the local timezone of a particular user.
You can localize date-time values by calling :data:`astimezone()` on a
:class:`datetime` object, passing in a :class:`tzinfo` object.

.. code-block:: python

    from datetime import timezone
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo


    # Function to localize datetimes. See also the pytz module.
    def localize(dt: datetime, tz: str):
        return dt.astimezone(ZoneInfo(tz))


    usa_user_timezone_setting = 'America/Los_Angeles'

    # Summer time in LA.
    domain_model_timestamp = datetime(2020, 6, 6, hour=12, tzinfo=timezone.utc)
    local_timestamp = localize(domain_model_timestamp, usa_user_timezone_setting)
    assert local_timestamp.hour == 5  # Seven hours behind.

    # Winter time in LA.
    domain_model_timestamp = datetime(2020, 1, 1, hour=12, tzinfo=timezone.utc)
    local_timestamp = localize(domain_model_timestamp, usa_user_timezone_setting)
    assert local_timestamp.hour == 4  # Daylight saving time.


    china_user_timezone_setting = 'Asia/Shanghai'

    # Summer time in Shanghai.
    domain_model_timestamp = datetime(2020, 6, 6, hour=12, tzinfo=timezone.utc)
    local_timestamp = localize(domain_model_timestamp, china_user_timezone_setting)
    assert local_timestamp.hour == 20  # Eight hours ahead.

    # Winter time in Shanghai.
    domain_model_timestamp = datetime(2020, 1, 1, hour=12, tzinfo=timezone.utc)
    local_timestamp = localize(domain_model_timestamp, china_user_timezone_setting)
    assert local_timestamp.hour == 20  # No daylight saving time in China.


However, if necessary, this default can be changed by assigning a :class:`tzinfo`
object to the :data:`TZINFO` attribute of the :mod:`eventsourcing.domain` module. The
:data:`TZINFO` value can be configured using environment variables, by setting the
environment variable ``TZINFO_TOPIC`` to a :ref:`topic string <Topics>` that locates
a Python :data:`tzinfo` object in your code, for example a :data:`timezone`
with an ``offset`` value, or a :data:``ZoneInfo`` from Python Standard Library with a
suitable ``key``. You need to set this environment variable before the
:mod:`eventsourcing.domain` is imported, or otherwise assign to the :data:`TZINFO`
attribute after that module has been imported. However, it is probably best to use
a timezone with a fixed offset from UTC, in which case you will probably still need
to convert to local time in the user interface. So it is strongly recommended to use
the default :data:`TZINFO`.

Please see the Python `docs <https://docs.python.org/3/library/zoneinfo.html>`_ for
more information about timezones, in particular the need to install :data:`tzdata`
on some systems. Please note, the ``zoneinfo`` package is new in Python 3.9, so users
of earlier versions of Python may wish to install the ``backports.zoneinfo`` package.

::

    $ pip install 'backports.zoneinfo;python_version<"3.9"'


Initial version number
======================

By default, the aggregates have an initial version number of ``1``. Sometimes it may be
desired, or indeed necessary, to use a different initial version number.

In the example below, the initial version number of the class ``MyAggregate`` is defined to be ``0``.

.. code-block:: python

    class MyAggregate(Aggregate):
        INITIAL_VERSION = 0

    aggregate = MyAggregate()
    assert aggregate.version == 0


If all aggregates in a domain model need to use the same non-default version number,
then a base class can be defined and used by the aggregates of the domain model on
which ``INITIAL_VERSION`` is set to the preferred value. Some people may wish to set
the preferred value on the library's :class:`~eventsourcing.domain.Aggregate` class.


.. _Topics:

Topic strings
=============

A 'topic' in this library is the path to a Python module (e.g. ``'eventsourcing.domain'``)
optionally followed by the qualified name of an object in that module (e.g. ``'Aggregate'``
or ``'Aggregate.Created'``), with these two parts joined with a colon character (``':'``).
For example, ``'eventsourcing.domain'`` is the topic of the library's domain module, and
``'eventsourcing.domain:Aggregate'`` is the topic of the :class:`~eventsourcing.domain.Aggregate`
class.

The library's :mod:`~eventsourcing.utils` module contains the functions
:func:`~eventsourcing.utils.resolve_topic` and :func:`~eventsourcing.utils.get_topic`
which are used in the library to resolve a given topic to a Python object, and to
construct a topic for a given Python object.

Topics are used when serialising domain events, to create references to domain event class
objects. Topic strings are also used in "created" events, to identify an aggregate class object.
Topics are also used to identify infrastructure factory class objects, and in other places too,
such as identifying the cipher and compressor classes to be used by an application, and to identify
the timezone object to be used when creating timestamps.

.. code-block:: python

    from eventsourcing.utils import get_topic, resolve_topic


    assert get_topic(Aggregate) == "eventsourcing.domain:Aggregate"
    assert resolve_topic("eventsourcing.domain:Aggregate") == Aggregate

    assert get_topic(Aggregate.Created) == "eventsourcing.domain:Aggregate.Created"
    assert resolve_topic("eventsourcing.domain:Aggregate.Created") == Aggregate.Created


Registering old topics
----------------------

The :func:`~eventsourcing.utils.register_topic` function
can be used to register an old topic for an object that has
been moved or renamed. When a class object is moved or renamed,
unless the old topic is registered, it will not be possible to
resolved an old topic. If an aggregate or event class is renamed,
it won't be possible to reconstruct instances from previously stored
events, unless the old topic is registered for the renamed class.

This also supports nested classes. For example, by registering an old
topic for a renamed aggregate, topics for nested classes that were created
using the old enclosing name will resolve to the same nested class on the
renamed enclosing class.

This will also work for renaming modules and packages. If a topic for
an old module name is registered for a renamed module, topics for
classes created under the old module name will resolve to the same
classes in the renamed module. And if a topic for an old package
name is registered for the renamed package, topics for classes created
under the old package name will resolve to same classes in the same
modules in the renamed package.

See the examples below.

..
    #include-when-testing
..
    eventsourcing.utils._topic_cache.clear()

.. code-block:: python

    from eventsourcing.utils import register_topic


    class MyAggregate(Aggregate):
        class Started(Aggregate.Created):
            pass


    # Current topics resolve.
    assert get_topic(MyAggregate) == "__main__:MyAggregate"
    assert resolve_topic("__main__:MyAggregate") == MyAggregate
    assert resolve_topic("__main__:MyAggregate.Started") == MyAggregate.Started

    # Aggregate class was renamed.
    register_topic("__main__:OldName", MyAggregate)
    assert resolve_topic("__main__:OldName") == MyAggregate
    assert resolve_topic("__main__:OldName.Started") == MyAggregate.Started

    # Nested event class was renamed.
    register_topic("__main__:MyAggregate.Created", MyAggregate.Started)
    assert resolve_topic("__main__:MyAggregate.Created") == MyAggregate.Started

    # Aggregate class was moved from another module.
    register_topic("eventsourcing.domain:MyAggregate", MyAggregate)
    assert resolve_topic("eventsourcing.domain:MyAggregate") == MyAggregate
    assert resolve_topic("eventsourcing.domain:MyAggregate.Created") == MyAggregate.Created
    assert resolve_topic("eventsourcing.domain:Aggregate") == Aggregate

    # Module was renamed.
    import eventsourcing.domain
    register_topic("eventsourcing.old", eventsourcing.domain)
    assert resolve_topic("eventsourcing.old:Aggregate") == Aggregate
    assert resolve_topic("eventsourcing.old:Aggregate.Created") == Aggregate.Created

    # Package was renamed.
    import eventsourcing
    register_topic("old", eventsourcing)
    assert resolve_topic("old.domain:Aggregate") == Aggregate
    assert resolve_topic("old.domain:Aggregate.Created") == Aggregate.Created

    # Current topics still resolve okay.
    assert get_topic(MyAggregate) == "__main__:MyAggregate"
    assert resolve_topic("__main__:MyAggregate") == MyAggregate
    assert resolve_topic("__main__:MyAggregate.Started") == MyAggregate.Started
    assert resolve_topic("eventsourcing.domain:Aggregate") == Aggregate


.. _Versioning:

Versioning
==========

Versioning allows aggregate and domain event classes to be modified after an application has been deployed.

On both aggregate and domain event classes, the class attribute ``class_version`` can be used to indicate
the version of the class. This attribute is inferred to have a default value of ``1``. If the data model is
changed, by adding or removing or renaming or changing the meaning of values of attributes, subsequent
versions should be given a successively higher number than the previously deployed version. Static methods
of the form ``upcast_vX_vY()`` will be called to update the state of a stored aggregate event or snapshot
from a lower version ``X`` to the next higher version ``Y``. Such upcast methods will be called to upcast
the state from the version of the class with which it was created to the version of the class which will
be reconstructed. For example, upcasting the stored state of an object created at version ``2`` of a
class that will be used to reconstruct an object at version ``4`` of the class will involve calling
upcast methods ``upcast_v2_v3()``, and ``upcast_v3_v4()``. If you aren't using snapshots, you don't
need to define upcast methods or version numbers on the aggregate class.

In the example below, version ``1`` of the class ``MyAggregate`` is defined with an attribute ``a``.

.. code-block:: python

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
upcast to have a value for ``b``.

In the example below, the static method ``upcast_v1_v2()`` defined
on the ``Created`` event sets a default value for ``b`` in the given ``state``. The class attribute
``class_version`` is set to ``2``. The same treatment is given to the aggregate class as the domain
event class, so that snapshots can be upcast.

.. code-block:: python

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
events will have been created and stored with both the ``a`` and ``b`` attributes. If subsequently the
attribute ``c`` is added to the definition of the ``Created`` event, in order for the existing stored
events from version 1 to be constructed in a way that satisfies the new version of the class, they
will need to be upcast to include a value for ``b`` and ``c``. The existing stored events from version 2
will need to be upcast to include a value for ``c``. The additional static method ``upcast_v2_v3()``
defined on the ``Created`` event sets a default value for ``c`` in the given ``state``. The class attribute
``class_version`` is set to ``3``. The same treatment is given to the aggregate class as the domain event
class, so that any snapshots will be upcast.

.. code-block:: python

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
when the aggregate is created, in order that snapshots from earlier versions will be upcast, the aggregate
class attribute ``class_version`` will need to be set to ``4`` and a static method ``upcast_v3_v4()`` will
need to be defined on the aggregate class which upcasts the state of a previously created snapshot.

In the example below, the new attribute ``d`` is initialised in the ``__init__()`` method, and an aggregate
event which updates ``d`` is defined. Since the ``Created`` event class has not changed, it remains at
version ``3``.

.. code-block:: python

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

            def apply(self, aggregate: Aggregate):
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


If the value object classes used by your events have also been adjusted, you may also need to define new
transcodings with new names. Simply register the new transcodings after the old transcodings, and use a
modified ``name`` value for the new transcoding. In this way, the already encoded values will be decoded
by the old transcoding, and the new instances of the value object class will be encoded and decoded with
the new version of the transcoding.

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
You are of course free to implement this in your code.


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

.. code-block:: python

    from eventsourcing.domain import Snapshot

The class method :func:`~eventsourcing.domain.Snapshot.take` can be used to
create a snapshot of an aggregate object.

.. code-block:: python

    snapshot = Snapshot.take(dog)

    assert isinstance(snapshot, Snapshot)
    assert snapshot.originator_id == dog.id
    assert snapshot.originator_version == dog.version
    assert snapshot.topic == "__main__:Dog", snapshot.topic
    assert snapshot.state["tricks"] == dog.tricks
    assert snapshot.state["_created_on"] == dog.created_on
    assert snapshot.state["_modified_on"] == dog.modified_on
    assert len(snapshot.state) == 3


A snapshot's :func:`~eventsourcing.domain.Snapshot.mutate` method can be used to reconstruct its
aggregate object instance.

.. code-block:: python

    copy = snapshot.mutate(None)

    assert isinstance(copy, Dog)
    assert copy.id == dog.id
    assert copy.version == dog.version
    assert copy.created_on == dog.created_on
    assert copy.modified_on == dog.modified_on
    assert copy.tricks == dog.tricks

The signature of the :func:`~eventsourcing.domain.Snapshot.mutate` method is the same as the
domain event object method of the same name, so that when reconstructing an aggregate, a list
that starts with a snapshot and continues with the subsequent domain event objects can be
treated in the same way as a list of all the domain event objects of an aggregate.
This similarity is needed by the application :ref:`repository <Repository>`, since
some specialist event stores (e.g. Axon Server) return a snapshot as the first domain event.


.. _Notes:


Notes
=====

Why put methods on event objects? There has been much discussion about the best way
to define the aggregate projectors. Of course, there isn't a "correct" way of doing it,
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
function as the aggregate projector for that type. When stored domain events are
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
be projected. And so, since there is an advantage to coding the aggregate projector
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
of saying everything three times, were resolved by the introduction of the :func:`@event<eventsourcing.domain.event>`
decorator as a more :ref:`declarative syntax <Declarative syntax>`. One criticism
of the declarative syntax design is that it is "command sourcing" and not "event sourcing",
because it is the command method arguments that are being used as the attributes of the
event. If may sometimes be "command sourcing" but then it is certainly also event
sourcing. Applications exist to support a domain, and in many cases applications support
the domain by recording decisions that are made in the domain and received by the domain model.
The :func:`@event<eventsourcing.domain.event>` decorator can also be used on "private" methods, methods that not part of the
aggregate's "public" command and query interface that will be used by the application, called
by "public" commands which are not so decorated, so do not trigger events that are simply
comprised of the method arguments, so then there is event sourcing but no command
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
aggregate objects in-place. This is a pattern we like, and returning an aggregate, or an
aggregate event, from an aggregate command method disrupts this pattern. The issue of
concurrent access doesn't arise unless the aggregates are cached and used concurrently
`without any concurrency controls`. Aggregates aren't cached by default in this library,
and so the issue doesn't arise, unless they are. And because it is in the nature of
aggregates that they create a sequence of events, there is no value to allowing concurrent
write access. But if aggregates are to be cached then it would make sense either to implement
suitable protection, such as locking, so that readers don't access a half-updated state and
so that writers don't interact, or for writers to make a deep copy of a cached aggregate before
calling aggregate commands, and then updating the cache with their mutated version after the
aggregate has been successfully saved, or for access to be otherwise serialized for example
by using the 'actor model' pattern. Care would also need to be taken to fast-forward an aggregate
that is stale because another process has advanced the state of the aggregate. But none of these
issues arise in the library because aggregates are not cached, they are local to the execution
of an application method.

Another issue arises about the use of "absolute" topics to identify classes. The issue
of moving and renaming classes can be resolved by setting the old paths to point to
current classes, using the library's methods for doing this. However, it maybe useful
to introduce support for "relative" topics, with the "base" topic left as application
configurable.

Classes
=======

.. automodule:: eventsourcing.domain
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members: __base_init__

.. automodule:: eventsourcing.utils
    :show-inheritance:
    :member-order: bysource
    :members:
