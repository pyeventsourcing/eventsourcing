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

A design pattern called "aggregate" is described in Eric Evans' book *Domain-Driven Design*:

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

The 'root' object of this cluster is an entity, and its identity is used
to uniquely identity of the aggregate in a domain model. External access to
the state of the aggregate is made through this root entity. The 'aggregate root'
has command and query methods which change and present the state of the aggregate.


.. _Aggregates:

Event-sourced aggregates
========================

Aggregates are enduring objects which enjoy adventures of change. For each
event-sourced aggregate, there is a sequence of domain event objects. The
state of an event-sourced aggregate is determined by its sequence of domain
event objects. The state of an aggregate can change, but the domain event
objects do not change. The notion of "change" is the contrast between
successive domain events.

The state of an aggregate is changed by calling its command methods. The command methods
create new domain event objects. The domain events are used to mutate the state of the
aggregate. By mutating the state of the aggregate via creating and applying domain events,
the domain events can be used in future to reconstruct the state of the aggregate.

One command may result in many new domain event objects, and a single client request may
result in the execution of many commands. To maintain consistency in the domain model,
the domain events triggered by responding to a client request must be recorded atomically
in the order they were created, otherwise the recorded state of the aggregate could become
inconsistent (with respect to that which was desired or expected). The atomic recording of
the domain model events defines the 'boundary' mentioned in the quote above. This boundary
is sometimes referred to as a 'consistency boundary'.

The library class :class:`~eventsourcing.domain.Aggregate` is a base class for event-sourced
aggregates. It can be used directly, or subclassed to develop event-sourced domain model aggregates
of different kinds.

.. code:: python

    from eventsourcing.domain import Aggregate

The :class:`~eventsourcing.domain.Aggregate` class defines a class method
:func:`~eventsourcing.domain.Aggregate._create` which can be called to create a new aggregate object. The
:func:`~eventsourcing.domain.Aggregate._create` method has
a required positional argument ``event_class``, which is used to pass a domain event
class that represents the creation of the aggregate. The :func:`~eventsourcing.domain.Aggregate._create`
method also has a required ``id`` argument which must be a Python :class:`~uuid.UUID` object that will be
used to uniquely identify the aggregate in the domain model. The
:func:`~eventsourcing.domain.Aggregate._create` method also accepts arbitrary keyword-only arguments,
which will be used to construct the "created" event object.

.. code:: python

    from uuid import uuid4

    aggregate = Aggregate._create(
        event_class=Aggregate.Created,
        id=uuid4(),
    )

The nested class :class:`~eventsourcing.domain.Aggregate.Created`
can be used directly, or subclassed to define custom "created" event classes for your aggregate
classes. The domain event classes are defined as Python frozen data classes. Hence, any extra
keyword arguments passed to the :func:`~eventsourcing.domain.Aggregate._create` method must be
matched by corresponding annotations on both the "created" domain event class and the aggregate
initializer :func:`~eventsourcing.domain.Aggregate.__init__`.

An aggregate instance has a version number, stored in its ``version`` attribute, and the initial
version is ``1``.

.. code:: python

    assert aggregate.version == 1


The :class:`~eventsourcing.domain.Aggregate` class defines an object method
:func:`~eventsourcing.domain.Aggregate._trigger_event` which can be called on an aggregate object
to create new domain events objects and apply them to the aggregate.
The :func:`~eventsourcing.domain.Aggregate._trigger_event` method has a positional argument
``event_class``, which is used to pass the object type of the new domain event object. The
:func:`~eventsourcing.domain.Aggregate._trigger_event` method also accepts arbitrary keyword-only
arguments, which will be used to construct the domain event object.

.. code:: python

    aggregate._trigger_event(
        event_class=Aggregate.Event,
    )

    assert aggregate.version == 2


The nested class :class:`~eventsourcing.domain.Aggregate.Event` can be subclassed to define custom
domain event classes, for example the ``SomethingHappened`` class in the example below.
Domain event classes are named using past participles, such as "Done", "Updated", "Closed",
etc. The extra keyword-only arguments passed to the :func:`~eventsourcing.domain.Aggregate._trigger_event`
method will become the attribute values of the created domain event object. Since the domain event
classes are defined as Python frozen data classes, the keyword-only arguments passed to the
:func:`~eventsourcing.domain.Aggregate._trigger_event` method will need to be matched by corresponding
annotations on your aggregates' domain event class definitions. For example ``what: str`` on the
``SomethingHappened`` event class in the example below matches the ``what=what`` keyword argument
passed in the call to the :func:`~eventsourcing.domain.Aggregate._trigger_event` method in the
``make_it_so()`` command. Triggering a new domain event object will increase the version of the
aggregate.

The :class:`~eventsourcing.domain.Aggregate` class defines an object method
:func:`~eventsourcing.domain.Aggregate.collect_events`
which can be called to collect the aggregate domain events that have been triggered but not yet recorded.
It is called without any arguments, and returns a list of all the domain events that have been created
by this aggregate since the previous call to :func:`~eventsourcing.domain.Aggregate.collect_events`.

.. code:: python

    pending_events = aggregate.collect_events()

    assert len(pending_events) == 2


The :class:`~eventsourcing.domain.Aggregate` class defines an object attribute ``id`` which holds the
unique ID of an aggregate instance. It is a Python :class:`~uuid.UUID`.

.. code:: python

    from uuid import UUID

    assert isinstance(aggregate.id, UUID)


The :class:`~eventsourcing.domain.Aggregate` class defines an object attribute ``version`` which holds
the version number of an aggregate instance. It is a Python :class:`int`.

.. code:: python

    assert isinstance(aggregate.version, int)


The :class:`~eventsourcing.domain.Aggregate` class defines an object attribute ``created_on`` which holds
the time when an aggregate object was created. It is a Python :class:`~datetime.datetime` object.

.. code:: python

    from datetime import datetime

    assert isinstance(aggregate.created_on, datetime)


The :class:`~eventsourcing.domain.Aggregate` class also defines an object attribute ``modified_on``
which holds the time when an aggregate object was last modified. It is also a Python
:class:`~datetime.datetime` object.

.. code:: python

    assert isinstance(aggregate.modified_on, datetime)

.. _Aggregate basic example:

Basic example
=============

In the example below, the ``World`` aggregate extends the library's
base class :class:`~eventsourcing.domain.Aggregate`.

The ``__init__()`` initializer method calls the ``super().__init__()``
method with the given ``**kwargs``, and then initialises a
``history`` attribute with an empty Python ``list`` object.

The ``create()`` method is a class method that creates and returns
a new ``World`` aggregate object. It uses the ``Created`` event class
as the value of the ``event_class`` argument. It uses a new version 4
:class:`~uuid.UUID` object as the value of the ``id`` argument.

The ``Created`` class is redefined. Although in this simple example
this ``World.Created`` event class carries no more attributes than the
base class event, it's always worth defining all event classes on the
concrete aggregate class itself in case these classes need to be modified
so that old instances can be upcast to new versions. Event class names
should express your project's ubiquitous language and take the grammatical
form of a past participle (either regular or irregular).

The ``make_it_so()`` method is a command method that triggers
a ``World.SomethingHappened`` domain event. The event is triggered
with the method argument ``what``.

The nested class ``SomethingHappened`` is a frozen data class that extends the
base aggregate event class ``Aggregate.Event`` (also a frozen data class) with a
field ``what`` which is defined as a Python :class:`str`. The ``apply()`` method
is implemented to append the ``what`` value to the aggregate's ``history``.


.. code:: python

    from dataclasses import dataclass
    from uuid import uuid4

    from eventsourcing.domain import Aggregate


    class World(Aggregate):
        def __init__(self, **kwargs):
            super(World, self).__init__(**kwargs)
            self.history = []

        @classmethod
        def create(cls):
            return cls._create(
                event_class=cls.Created,
                id=uuid4(),
            )

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


We can create a new ``World`` aggregate object by calling the
``World.create()`` class method.

.. code:: python

    # Create new world.
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
command, the argument ``what`` will be appended to the ``history``. By mutating
the state of the aggregate via triggering and applying domain events, the domain
events can be used in future to reconstruct the state of the aggregate.

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


The domain events' :func:`~eventsourcing.domain.Aggregate.Event.mutate` methods can
be used to reconstruct a copy of the original aggregate object. And indeed the
:ref:`repository <Repository>` object has a
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


.. _Events:

Domain events
=============

Domain event objects represent decisions by the domain model. Domain events are created
but do not change.

The nested base class for aggregate events, :class:`~eventsourcing.domain.Aggregate.Event`,
is defined to have attributes ``originator_id`` which is a Python :class:`~uuid.UUID`, an
``originator_version`` which is a Python :class:`int`, and ``timestamp`` which is a Python
:class:`~datetime.datetime`.

The :class:`~eventsourcing.domain.Aggregate.Event` has a method
:func:`~eventsourcing.domain.Aggregate.Event.apply` which can be overridden on custom domain
event classes to mutate the state of the aggregate to which a domain event object pertains. It
has an argument ``aggregate`` which is used to pass the aggregate object to which the domain
event object pertains into the :func:`~eventsourcing.domain.Aggregate.Event.apply` method. The
:func:`~eventsourcing.domain.Aggregate.Event.apply` method is called by the event's
:func:`~eventsourcing.domain.Aggregate.Event.mutate` method, which is called when
reconstructing an aggregate from its events.

The nested class :class:`~eventsourcing.domain.Aggregate.Created` represents the creation of
an aggregate object instance. It extends the base class :class:`~eventsourcing.domain.Aggregate.Event`
with its attribute ``originator_topic`` which is Python :class:`str`. The value of this attribute
will be a :ref:`topic <Topics>` that describes the path to the aggregate instance's class.

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

.. code:: python

    from eventsourcing.domain import Snapshot

The class method :func:`~eventsourcing.domain.Snapshot.take` can be used to
create a snapshot of an aggregate object instance. See the
discussion of :ref:`snapshotting <Snapshotting>` in the application
module documentation for more information.

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
This convenience is used by the application :ref:`repository <Repository>`.


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
single sequence. And so using an index aggregate with an ID that can be recreated
from a mutable attribute value to hold the ID of the aggregate with the mutable
attribute value makes it possible to identify the aggregate from the current
attribute value.

For example, if you have a collection of page aggregates with names that might change,
and you want to be able to identify the pages by name, then you can create index
aggregates with version 5 UUIDs that are generated from the names, and put the IDs
of the page aggregates in the index aggregates. The classes :class:`Page` and :class:`Index`
in the example code below shows how this can be done using event-sourced aggregates.

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
    from uuid import uuid5, NAMESPACE_URL

    from eventsourcing.domain import Aggregate


    class Page(Aggregate):
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

        def __init__(self, name: str, body: str, **kwargs):
            super(Page, self).__init__(**kwargs)
            self.name = name
            self.body = body

        def update_name(self, name: str):
            self._trigger_event(self.NameUpdated, name=name)

        @dataclass(frozen=True)
        class NameUpdated(Aggregate.Event):
            name: str

            def apply(self, page: "Page"):
                page.name = self.name


    class Index(Aggregate):
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

        @classmethod
        def create_id(cls, name: str):
            return uuid5(NAMESPACE_URL, f"/pages/{name}")

        def __init__(self, ref, **kwargs):
            super().__init__(**kwargs)
            self.ref = ref

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
the :ref:`Event-sourced applications <Application objects>` documentation.

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
