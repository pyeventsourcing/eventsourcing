============
Domain model
============

The library's domain layer has base classes for domain events and entities. These classes show how to
write a domain model that uses the library's event sourcing infrastructure. They can also be used to
develop an event-sourced application as a domain driven design.

.. contents:: :local:


Domain events
=============

The purpose of a domain event is to be published when something happens, normally the results from the
work of a command. The library has a base class for domain events called ``DomainEvent``.

Domain events can be freely constructed from the ``DomainEvent`` class. Attributes are
set directly from the constructor keyword arguments.

.. code:: python

    from eventsourcing.domain.model.events import DomainEvent

    domain_event = DomainEvent(a=1)
    assert domain_event.a == 1


The attributes of domain events are read-only. New values cannot be assigned to existing objects.
Domain events are immutable in that sense.

.. code:: python

    # Fail to set attribute of already-existing domain event.
    try:
        domain_event.a = 2
    except AttributeError:
        pass
    else:
        raise Exception("Shouldn't get here")


Domain events can be compared for equality as value objects, instances are equal if they have the
same type and the same attributes.

.. code:: python

    DomainEvent(a=1) == DomainEvent(a=1)

    DomainEvent(a=1) != DomainEvent(a=2)

    DomainEvent(a=1) != DomainEvent(b=1)


Publish-subscribe
-----------------

Domain events can be published, using the library's publish-subscribe mechanism.

The ``publish()`` function is used to publish events. The ``event`` arg is required.

.. code:: python

    from eventsourcing.domain.model.events import publish

    publish(event=domain_event)


The ``subscribe()`` function is used to subscribe a ``handler`` that will receive events.

The optional ``predicate`` arg can be used to provide a function that will decide whether
or not the subscribed handler will actually be called when an event is published.

.. code:: python

    from eventsourcing.domain.model.events import subscribe

    received_events = []

    def receive_event(event):
        received_events.append(event)

    def is_domain_event(event):
        return isinstance(event, DomainEvent)

    subscribe(handler=receive_event, predicate=is_domain_event)

    # Publish the domain event.
    publish(domain_event)

    assert len(received_events) == 1
    assert received_events[0] == domain_event


The ``unsubscribe()`` function can be used to stop the handler receiving further events.

.. code:: python

    from eventsourcing.domain.model.events import unsubscribe

    unsubscribe(handler=receive_event, predicate=is_domain_event)

    # Clean up.
    del received_events[:]  # received_events.clear()


Event library
-------------

The library has a small collection of domain event subclasses, such as ``EventWithOriginatorID``,
``EventWithOriginatorVersion``, ``EventWithTimestamp``, ``EventWithTimeuuid``, ``Created``, ``AttributeChanged``,
``Discarded``.

Some of these classes provide useful defaults for particular attributes, such as a ``timestamp``.
Timestamps can be used to sequence events.

.. code:: python

    from eventsourcing.domain.model.events import EventWithTimestamp
    from eventsourcing.domain.model.events import EventWithTimeuuid
    from decimal import Decimal
    from uuid import UUID

    # Automatic timestamp.
    assert isinstance(EventWithTimestamp().timestamp, Decimal)

    # Automatic UUIDv1.
    assert isinstance(EventWithTimeuuid().event_id, UUID)


Some classes require particular arguments when constructed. The ``originator_id`` can be used
to identify a sequence to which an event belongs. The ``originator_version`` can be used to
position the event in a sequence.

.. code:: python

    from eventsourcing.domain.model.events import EventWithOriginatorVersion
    from eventsourcing.domain.model.events import EventWithOriginatorID
    from uuid import uuid4

    # Requires originator_id.
    EventWithOriginatorID(originator_id=uuid4())

    # Requires originator_version.
    EventWithOriginatorVersion(originator_version=0)


Some are just useful for their distinct type, for example in subscription predicates.

.. code:: python

    from eventsourcing.domain.model.events import Created, AttributeChanged, Discarded

    def is_created(event):
        return isinstance(event, Created)

    def is_attribute_changed(event):
        return isinstance(event, AttributeChanged)

    def is_discarded(event):
        return isinstance(event, Discarded)

    assert is_created(Created()) is True
    assert is_created(Discarded()) is False
    assert is_created(DomainEvent()) is False

    assert is_discarded(Created()) is False
    assert is_discarded(Discarded()) is True
    assert is_discarded(DomainEvent()) is False

    assert is_domain_event(Created()) is True
    assert is_domain_event(Discarded()) is True
    assert is_domain_event(DomainEvent()) is True


Custom events
-------------

Custom domain events can be coded by subclassing the library's domain event classes.

Domain events are normally named using the past participle of a common verb, for example
a regular past participle such as "started", "paused", "stopped", or an irregular past
participle such as "chosen", "done", "found", "paid", "quit", "seen".

.. code:: python

    class SomethingHappened(DomainEvent):
        """
        Published whenever something happens.
        """


It is possible to code domain events as inner or nested classes.

.. code:: python

    class Job(object):

        class Seen(EventWithTimestamp):
            """
            Published when the job is seen.
            """

        class Done(EventWithTimestamp):
            """
            Published when the job is done.
            """

Inner or nested classes can be used, and are used in the library, to define
the domain events of a domain entity on the entity class itself.

.. code:: python

    seen = Job.Seen(job_id='#1')
    done = Job.Done(job_id='#1')

    assert done.timestamp > seen.timestamp


So long as the entity event classes inherit ultimately from library class
``QualnameABC``, which ``DomainEvent`` does, the utility functions ``get_topic()``
and ``resolve_topic()`` can work with domain events defined as inner or nested
classes in all versions of Python. These functions are used in the ``DomainEntity.Created``
event class, and in the infrastructure class ``SequencedItemMapper``. The requirement
to inherit from ``QualnameABC`` actually only applies when using nested classes in Python 2.7
with the utility functions ``get_topic()`` and ``resolve_topic()``. Events classes that
are not nested, or that will not be run with Python 2.7, do not need to
inherit from ``QualnameABC`` in order to work with these two functions (and
hence the library domain and infrastructure classes which use those functions).


Domain entities
===============

A domain entity is an object that is not defined by its attributes, but rather by a thread of continuity and its
identity. The attributes of a domain entity can change, directly by assignment, or indirectly by calling a method of
the object.

The library has a base class for domain entities called ``DomainEntity``, which has an ``id`` attribute.

.. code:: python

    from eventsourcing.domain.model.entity import DomainEntity

    entity_id = uuid4()

    entity = DomainEntity(id=entity_id)

    assert entity.id == entity_id


Entity library
--------------

The library also has a domain entity class called ``VersionedEntity``, which extends the ``DomainEntity`` class
with a ``__version__`` attribute.

.. code:: python

    from eventsourcing.domain.model.entity import VersionedEntity

    entity = VersionedEntity(id=entity_id, __version__=1)

    assert entity.id == entity_id
    assert entity.__version__ == 1


The library also has a domain entity class called ``TimestampedEntity``, which extends the ``DomainEntity`` class
with attributes ``__created_on__`` and ``__last_modified__``.

.. code:: python

    from eventsourcing.domain.model.entity import TimestampedEntity

    entity = TimestampedEntity(id=entity_id, __created_on__=123)

    assert entity.id == entity_id
    assert entity.__created_on__ == 123
    assert entity.__last_modified__ == 123


There is also a ``TimestampedVersionedEntity`` that has ``id``, ``__version__``, ``__created_on__``, and ``__last_modified__``
attributes.

.. code:: python

    from eventsourcing.domain.model.entity import TimestampedVersionedEntity

    entity = TimestampedVersionedEntity(id=entity_id, __version__=1, __created_on__=123)

    assert entity.id == entity_id
    assert entity.__created_on__ == 123
    assert entity.__last_modified__ == 123
    assert entity.__version__ == 1


A timestamped, versioned entity is both a timestamped entity and a versioned entity.

.. code:: python

    assert isinstance(entity, TimestampedEntity)
    assert isinstance(entity, VersionedEntity)


Naming style
------------

The double leading and trailing underscore naming style, seen above,
is used consistently in the library's domain entity and event
base classes for attribute and method names, so that developers can
begin with a clean namespace. The intention is that the library
functionality is included in the application by aliasing these library
names with names that work within the project's ubiquitous language.

This style breaks PEP8, but it seems worthwhile in order to keep the
"normal" Python object namespace free for domain modelling. It is a style
used by other libraries (such as SQLAlchemy and Django) for similar reasons.

The exception is the ``id`` attribute of the domain entity base class,
which is assumed to be required by all domain entities (or aggregates) in
all domains.


Entity events
-------------

The library's domain entity classes have domain events defined as inner
classes: ``Event``, ``Created``, ``AttributeChanged``, and ``Discarded``.

.. code:: python

    DomainEntity.Event
    DomainEntity.Created
    DomainEntity.AttributeChanged
    DomainEntity.Discarded


The domain event class ``DomainEntity.Event`` is a super type of the others.
The others also inherit from the library base classes ``Created``,
``AttributeChanged``, and ``Discarded``. All these domain events classes
are subclasses of ``DomainEvent``.

.. code:: python

    assert issubclass(DomainEntity.Created, DomainEntity.Event)
    assert issubclass(DomainEntity.AttributeChanged, DomainEntity.Event)
    assert issubclass(DomainEntity.Discarded, DomainEntity.Event)

    assert issubclass(DomainEntity.Created, Created)
    assert issubclass(DomainEntity.AttributeChanged, AttributeChanged)
    assert issubclass(DomainEntity.Discarded, Discarded)

    assert issubclass(DomainEntity.Event, DomainEvent)


These entity event classes can be freely constructed, with
suitable arguments.

All events need an ``originator_id``. Events of versioned entities also
need an ``originator_version``. Events of timestamped entities generate
a current ``timestamp`` value, unless one is given. ``Created`` events
also need an ``originator_topic``. The other events need an ``__previous_hash__``.
``AttributeChanged`` events also need ``name`` and ``value``.

All the events of ``DomainEntity`` use SHA-256 to generate an ``event_hash``
from the event attribute values when constructed for the first time. Events
can be chained together by constructing each subsequent event to have its
``__previous_hash__`` as the ``event_hash`` of the previous event.

.. code:: python

    from eventsourcing.utils.topic import get_topic

    entity_id = UUID('b81d160d-d7ef-45ab-a629-c7278082a845')

    created = VersionedEntity.Created(
        originator_version=0,
        originator_id=entity_id,
        originator_topic=get_topic(VersionedEntity)
    )

    attribute_a_changed = VersionedEntity.AttributeChanged(
        name='a',
        value=1,
        originator_version=1,
        originator_id=entity_id,
    )

    attribute_b_changed = VersionedEntity.AttributeChanged(
        name='b',
        value=2,
        originator_version=2,
        originator_id=entity_id,
    )

    entity_discarded = VersionedEntity.Discarded(
        originator_version=3,
        originator_id=entity_id,
    )


The events have a ``__mutate__()`` function, which can be used to mutate the
state of a given object appropriately.

For example, the ``DomainEntity.Created`` event mutates to an
entity instance. The class that is instantiated is determined by the
``originator_topic`` attribute of the ``DomainEntity.Created`` event.

A domain event's ``__mutate__()`` method normally requires an ``obj`` argument, but
that is not required for ``DomainEntity.Created`` events. The default
is ``None``, but if a value is provided it must be callable that
returns an object, such as a domain entity class. If a domain
entity class is provided, the ``originator_topic`` will be ignored.

.. code:: python

    entity = created.__mutate__()

    assert entity.id == entity_id


As another example, when a versioned entity is mutated by an event of the
``VersionedEntity`` class, the entity version number is set to the event
``originator_version``.

.. code:: python

    assert entity.__version__ == 0

    entity = attribute_a_changed.__mutate__(entity)
    assert entity.__version__ == 1
    assert entity.a == 1

    entity = attribute_b_changed.__mutate__(entity)
    assert entity.__version__ == 2
    assert entity.b == 2


Similarly, when a timestamped entity is mutated by an event of the
``TimestampedEntity`` class, the ``__last_modified__`` attribute of the
entity is set to have the event's ``timestamp`` value.


Factory method
--------------

The ``DomainEntity`` has a class method ``__create__()`` which can return
new entity objects. When called, it constructs the ``Created`` event of the
concrete class with suitable arguments such as a unique ID, and a topic representing
the concrete entity class, and then it projects that event into an entity
object using the event's ``__mutate__()`` method. Then it publishes the
event, and then it returns the new entity to the caller. This technique
works correctly for subclasses of both the entity and the event class.

.. code:: python

    entity = DomainEntity.__create__()
    assert entity.id
    assert entity.__class__ is DomainEntity


    entity = VersionedEntity.__create__()
    assert entity.id
    assert entity.__version__ == 0
    assert entity.__class__ is VersionedEntity


    entity = TimestampedEntity.__create__()
    assert entity.id
    assert entity.__created_on__
    assert entity.__last_modified__
    assert entity.__class__ is TimestampedEntity


    entity = TimestampedVersionedEntity.__create__()
    assert entity.id
    assert entity.__created_on__
    assert entity.__last_modified__
    assert entity.__version__ == 0
    assert entity.__class__ is TimestampedVersionedEntity


Triggering events
-----------------

Commands methods will construct, apply, and publish events, using the results from working
on command arguments. The events need to be constructed with suitable arguments.

To help trigger events in an extensible manner, the ``DomainEntity`` class has a
method called ``__trigger_event__()``, that is extended by subclasses in the library,
which can be used in command  methods to construct, apply, and publish events with
suitable arguments. The events' ``__mutate__()`` methods update the entity appropriately.

For example, triggering an ``AttributeChanged`` event on a timestamped, versioned
entity will cause the attribute value to be updated, but it will also
cause the version number to increase, and it will update the last modified time.

.. code:: python

    entity = TimestampedVersionedEntity.__create__()
    assert entity.__version__ == 0
    assert entity.__created_on__ == entity.__last_modified__

    # Trigger domain event.
    entity.__trigger_event__(entity.AttributeChanged, name='c', value=3)

    # Check the event was applied.
    assert entity.c == 3
    assert entity.__version__ == 1
    assert entity.__last_modified__ > entity.__created_on__


The command method ``__change_attribute__()`` triggers an
``AttributeChanged`` event. In the code below, the attribute ``full_name``
is set to 'Mr Boots'. A subscriber receives the event.

.. code:: python

    subscribe(handler=receive_event, predicate=is_domain_event)
    assert len(received_events) == 0

    entity = VersionedEntity.__create__(entity_id)

    # Change an attribute.
    entity.__change_attribute__(name='full_name', value='Mr Boots')

    # Check the event was applied.
    assert entity.full_name == 'Mr Boots'

    # Check two events were published.
    assert len(received_events) == 2

    first_event = received_events[0]
    assert first_event.__class__ == VersionedEntity.Created
    assert first_event.originator_id == entity_id
    assert first_event.originator_version == 0

    last_event = received_events[1]
    assert last_event.__class__ == VersionedEntity.AttributeChanged
    assert last_event.name == 'full_name'
    assert last_event.value == 'Mr Boots'
    assert last_event.originator_version == 1

    # Clean up.
    unsubscribe(handler=receive_event, predicate=is_domain_event)
    del received_events[:]  # received_events.clear()


Discarding entities
-------------------

The entity method ``__discard__()`` can be used to discard the entity, by triggering
a ``Discarded`` event, after which the entity is unavailable for further changes.

.. code:: python

    from eventsourcing.exceptions import EntityIsDiscarded

    entity.__discard__()

    # Fail to change an attribute after entity was discarded.
    try:
        entity.__change_attribute__('full_name', 'Mr Boots')
    except EntityIsDiscarded:
        pass
    else:
        raise Exception("Shouldn't get here")


Custom entities
---------------

The library entity classes can be subclassed.

.. code:: python

    class User(VersionedEntity):
        def __init__(self, full_name, *args, **kwargs):
            super(User, self).__init__(*args, **kwargs)
            self.full_name = full_name


Subclasses can extend the entity base classes, by adding event-based properties and methods.


Custom attributes
-----------------

The library's ``@attribute`` decorator provides a property getter and setter, which will triggers an
``AttributeChanged`` event when the property is assigned. Simple mutable attributes can be coded as
decorated functions without a body, such as the ``full_name`` function of ``User`` below.

.. code:: python

    from eventsourcing.domain.model.decorators import attribute


    class User(VersionedEntity):

        def __init__(self, full_name, *args, **kwargs):
            super(User, self).__init__(*args, **kwargs)
            self._full_name = full_name

        @attribute
        def full_name(self):
            """Full name of the user."""


In the code below, after the entity has been created, assigning to the ``full_name`` attribute causes
the entity to be updated. An ``AttributeChanged`` event is published. Both the ``Created`` and
``AttributeChanged`` events are received by a subscriber.

.. code:: python

    assert len(received_events) == 0
    subscribe(handler=receive_event, predicate=is_domain_event)

    # Publish a Created event.
    user = User.__create__(full_name='Mrs Boots')

    # Publish an AttributeChanged event.
    user.full_name = 'Mr Boots'

    assert len(received_events) == 2
    assert received_events[0].__class__ == VersionedEntity.Created
    assert received_events[0].full_name == 'Mrs Boots'
    assert received_events[0].originator_version == 0
    assert received_events[0].originator_id == user.id

    assert received_events[1].__class__ == VersionedEntity.AttributeChanged
    assert received_events[1].value == 'Mr Boots'
    assert received_events[1].name == '_full_name'
    assert received_events[1].originator_version == 1
    assert received_events[1].originator_id == user.id

    # Clean up.
    unsubscribe(handler=receive_event, predicate=is_domain_event)
    del received_events[:]  # received_events.clear()


Custom commands
---------------

The entity base classes can be extended with custom command methods. In general,
the arguments of a command will be used to perform some work. Then, the result
of the work will be used to trigger a domain event that represents what happened.
Please note, command methods normally have no return value.

For example, the ``set_password()`` method of the ``User`` entity below is given
a raw password. It creates an encoded string from the raw password, and then uses
the ``__change_attribute__()`` method to trigger an ``AttributeChanged`` event for
the ``_password`` attribute with the encoded password.

.. code:: python

    from eventsourcing.domain.model.decorators import attribute


    class User(VersionedEntity):

        def __init__(self, *args, **kwargs):
            super(User, self).__init__(*args, **kwargs)
            self._password = None

        def set_password(self, raw_password):
            # Do some work using the arguments of a command.
            password = self._encode_password(raw_password)

            # Change private _password attribute.
            self.__change_attribute__('_password', password)

        def check_password(self, raw_password):
            password = self._encode_password(raw_password)
            return self._password == password

        def _encode_password(self, password):
            return ''.join(reversed(password))


    user = User(id='1', __version__=0)

    user.set_password('password')
    assert user.check_password('password')


Custom events
-------------

Custom events can be defined as inner or nested classes of the custom entity class.
In the code below, the entity class ``World`` has a custom event called ``SomethingHappened``.

Custom event classes can extend the ``__mutate__()`` method, so it affects
entities in a way that is specific to that type of event. More conveniently, event
classes can implement a ``mutate()`` method, which avoids the need to call the
super method and return the obj. For example, the ``SomethingHappened`` event class
has a ``mutate()`` method which simply appends the event object to the entity's ``history``
attribute.

Custom events are normally triggered by custom commands. In the example below,
the command method ``make_it_so()`` triggers the custom event ``SomethingHappened``.

.. code:: python

    from eventsourcing.domain.model.decorators import mutator

    class World(VersionedEntity):

        def __init__(self, *args, **kwargs):
            super(World, self).__init__(*args, **kwargs)
            self.history = []

        def make_it_so(self, something):
            # Do some work using the arguments of a command.
            what_happened = something

            # Trigger event with the results of the work.
            self.__trigger_event__(World.SomethingHappened, what=what_happened)

        class SomethingHappened(VersionedEntity.Event):
            """Published when something happens in the world."""
            def mutate(self, obj):
                obj.history.append(self)


A new world can now be created, using the ``__create__()`` method. The command ``make_it_so()`` can
be used to make things happen in this world. When something happens, the history of the world
is augmented with the new event.

.. code:: python

    world = World.__create__()

    world.make_it_so('dinosaurs')
    world.make_it_so('trucks')
    world.make_it_so('internet')

    assert world.history[0].what == 'dinosaurs'
    assert world.history[1].what == 'trucks'
    assert world.history[2].what == 'internet'


Aggregate root
==============

Eric Evans' book Domain Driven Design describes an abstraction called
"aggregate":

.. pull-quote::

    *"An aggregate is a cluster of associated objects that we treat as a unit
    for the purpose of data changes. Each aggregate has a root and a boundary."*

Therefore,

.. pull-quote::

    *"Cluster the entities and value objects into aggregates and define
    boundaries around each. Choose one entity to be the root of each
    aggregate, and control all access to the objects inside the boundary
    through the root. Allow external objects to hold references to the
    root only."*

In this situation, one aggregate command may result in many events.
In order to construct a consistency boundary, we need to prevent the
situation where other threads pick up only some of the events, but not
all of them, which could present the aggregate in an inconsistent, or
unusual, and perhaps unworkable state.

In other words, we need to avoid the situation where some of the events
have been stored successfully but others have not been. If the events
from a command were stored in a series of independent database transactions,
then some would be written before others. If another thread needs the
aggregate and gets its events whilst a series of new event are being written,
it would not receive some of the events, but not the events that have not yet
been written. Worse still, events could be lost due to an inconvenient database
server problem, or sudden termination of the client. Even worse, later events
in the series could fall into conflict because another thread has started
appending events to the same sequence, potentially causing an incoherent state
that would be difficult to repair.

Therefore, to implement the aggregate as a consistency boundary, all the events
from a command on an aggregate must be appended to the event store in a single
atomic transaction, so that if some of the events resulting from executing a
command cannot be stored then none of them will be stored. If all the events
from an aggregate are to be written to a database as a single atomic operation,
then they must have been published by the entity as a single list.

The library has a domain entity class called
:class:`~eventsourcing.domain.model.aggregate.AggregateRoot` that can be
useful in a domain driven design, especially where a single command can cause
many events to be published. The ``AggregateRoot`` entity class extends
``TimestampedVersionedEntity``. It overrides the ``__publish__()`` method of
the base class, so that triggered events are published only to a private list
of pending events, rather than directly to the publish-subscribe mechanism. It
also adds a method called ``__save__()``, which publishes all
pending events to the publish-subscribe mechanism as a single list.

It can be subclassed by custom aggregate root entities. In the example below, the
entity class ``World`` inherits from ``AggregateRoot``.

.. code:: python

    from eventsourcing.domain.model.aggregate import AggregateRoot


    class World(AggregateRoot):
        """
        Example domain entity, with mutator function on domain event.
        """
        def __init__(self, *args, **kwargs):
            super(World, self).__init__(*args, **kwargs)
            self.history = []

        def make_things_so(self, *somethings):
            for something in somethings:
                self.__trigger_event__(World.SomethingHappened, what=something)

        class SomethingHappened(AggregateRoot.Event):
            def mutate(self, obj):
                obj.history.append(self)


The ``World`` aggregate root has a command method ``make_things_so()`` which publishes
``SomethingHappened`` events. The ``mutate()`` method of the ``SomethingHappened`` class
simply appends the event (``self``) to the aggregate object ``obj``.

We can see the events that are published by subscribing to the handler ``receive_events()``.

.. code:: python

    assert len(received_events) == 0
    subscribe(handler=receive_event)

    # Create new world.
    world = World.__create__()
    assert isinstance(world, World)

    # Command that publishes many events.
    world.make_things_so('dinosaurs', 'trucks', 'internet')

    # State of aggregate object has changed
    # but no events have been published yet.
    assert len(received_events) == 0
    assert world.history[0].what == 'dinosaurs'
    assert world.history[1].what == 'trucks'
    assert world.history[2].what == 'internet'


Events are pending, and will not be published until the ``__save__()`` method is called.

.. code:: python

    # Has pending events.
    assert len(world.__pending_events__) == 4

    # Publish pending events.
    world.__save__()

    # Pending events published as a list.
    assert len(received_events) == 1
    assert len(received_events[0]) == 4

    # No longer any pending events.
    assert len(world.__pending_events__) == 0

Data integrity
--------------

Domain events triggered by the library's ``AggregateRoot`` class are both hashed and
also hash-chained together.

The state of each event, including the hash of the previous event, is hashed using
SHA-256. The state of each event can be validated as a part of the chain. If the
sequence of events is accidentally damaged in any way, then a ``DataIntegrityError``
will almost certainly be raised from the domain layer when the sequence is replayed.

The hash of the last event applied to an aggregate root is available as an attribute called
``__head__`` of the aggregate root.

.. code:: python

    # Entity's head hash is determined exclusively
    # by the entire sequence of events and SHA-256.
    assert world.__head__ == received_events[0][-1].__event_hash__


A different sequence of events will almost certainly result a different
head hash. So the entire history of an entity can be verified by checking the
head hash against an independent record.

The hashes can be salted by setting environment variable ``SALT_FOR_DATA_INTEGRITY``,
perhaps with random bytes encoded as Base64.

.. code:: python

    from eventsourcing.utils.random import encode_random_bytes

    # Keep this safe.
    salt = encode_random_bytes(num_bytes=32)

    # Configure environment (before importing library).
    import os
    os.environ['SALT_FOR_DATA_INTEGRITY'] = salt


The "genesis hash" used as the previous hash of the first event in a sequence can be
set using environment variable ``GENESIS_HASH``.

    # Clean up.
    unsubscribe(handler=receive_event)
    del received_events[:]  # received_events.clear()
