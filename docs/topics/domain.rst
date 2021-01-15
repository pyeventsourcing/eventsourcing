=============================================
:mod:`eventsourcing.domain` --- Domain models
=============================================


This module helps with developing event-sourced domain models.
It includes a base class for event-sourced aggregates that can be
used to develop an event-sourced domain model. Event sourced aggregates
depend on domain events, and so the aggregate class has a nested event class
that can be used to define aggregate events.

There is also a snapshot class, which can be used to store the current state
of an aggregate. Snapshots improve the time needed to reconstruct an aggregate,
by avoiding the need to retrieve and apply all the domain events of an aggregate
to reconstruct an aggregate object.

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
in many events, and also responding to a client request may result in more than one
command. In order to construct a consistency boundary, we need to record the domain
events that are triggered by responding to a client request atomically atomically,
otherwise the recorded state of the aggregate could become undesirable, or
inconsistent, or unusual, or unworkable. The atomic recording of the changes to
an aggregate defines the consistency 'boundary'.


Event-sourced aggregates
========================

The library's :class:`~eventsourcing.domain.Aggregate` class can be subclassed to develop
event-sourced domain model aggregates. The nested class
:class:`~eventsourcing.domain.Aggregate.Event` can be subclassed to define domain event
classes that will be triggered by the command methods of the domain model aggregates. The
class method ``_create_()`` can be called to help with the creation of a new aggregate.
The object method ``_trigger_()`` can be called to help with the triggering of domain
events. The domain event classes are Python frozen data classes, so the attributes they
will have need to be defined as annotations on the class. The ``event_class`` positional
argument of the ``_trigger_()`` method is used to pass the type of the domain event that
will be triggered, and the attribute values that the event will have are passed as
keyword-only arguments.

.. code:: python

    from uuid import uuid4

    from eventsourcing.domain import Aggregate


    class World(Aggregate):
        def __init__(self, **kwargs):
            super(World, self).__init__(**kwargs)
            self.history = []

        @classmethod
        def create(cls):
            return cls._create_(
                event_class=cls.Created,
                uuid=uuid4(),
            )

        def make_it_so(self, what):
            self._trigger_(World.SomethingHappened, what=what)

        class SomethingHappened(Aggregate.Event):
            what: str

            def apply(self, world):
                world.history.append(self.what)


The ``World`` class method ``create()`` can be used to create a new
aggregate object.

.. code:: python

    # Create new world.
    world = World.create()
    assert isinstance(world, World)

The attributes ``created_on`` and ``modified_on`` show when the aggregate
was created and when it was modified. Since there has only been one
domain event, these are initially equal. The values of these attributes
are Python datetime objects. These values follow from the ``timestamp``
values of the domain event objects, and represent when the aggregate's
first and last domain events were created.

.. code:: python

    from datetime import datetime

    assert world.created_on == world.modified_on
    assert isinstance(world.created_on, datetime)


The ``World`` aggregate has a command method ``make_it_so()`` which
triggers the ``SomethingHappened`` event. The ``mutate()`` method of
the ``SomethingHappened`` class appends the ``what`` of the event to
the ``history`` of the ``world``.

.. code:: python

    # Commands methods trigger events.
    world.make_it_so('dinosaurs')
    world.make_it_so('trucks')
    world.make_it_so('internet')

    # State of aggregate object has changed.
    assert world.history[0] == 'dinosaurs'
    assert world.history[1] == 'trucks'
    assert world.history[2] == 'internet'


Now that more than one domain event has been created, the ``world``
aggregate's ``created_on`` value is less than its ``modified_on`` value.

.. code:: python

    assert world.created_on < world.modified_on


The resulting domain events are now held internally in the aggregate in
a list of pending events. They can be collected by calling the ``collect()``
method. So far, we have created four domain events and we have not yet collected
them, and so there will be four pending events: the ``Created`` event, and
three ``SomethingHappened`` events.

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


The domain events' ``mutate()`` methods can be used to reconstruct the
aggregate object.

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


Classes
=======

.. automodule:: eventsourcing.domain
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__
