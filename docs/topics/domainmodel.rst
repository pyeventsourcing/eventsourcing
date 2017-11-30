============
Domain model
============

The library's domain layer has base classes for domain events and entities. These classes show how to
write a domain model that uses the library's event sourcing infrastructure. They can also be used to
develop an event-sourced application as a domain driven design.


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
    from uuid import UUID

    # Automatic timestamp.
    assert isinstance(EventWithTimestamp().timestamp, float)

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

    from eventsourcing.domain.model.events import Created, Discarded

    def is_created(event):
        return isinstance(event, Created)

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
with a ``version`` attribute.

.. code:: python

    from eventsourcing.domain.model.entity import VersionedEntity

    entity = VersionedEntity(id=entity_id, version=1)

    assert entity.id == entity_id
    assert entity.version == 1


The library also has a domain entity class called ``TimestampedEntity``, which extends the ``DomainEntity`` class
with a ``created_on`` and ``last_modified`` attributes.

.. code:: python

    from eventsourcing.domain.model.entity import TimestampedEntity

    entity = TimestampedEntity(id=entity_id, timestamp=123)

    assert entity.id == entity_id
    assert entity.created_on == 123
    assert entity.last_modified == 123


There is also a ``TimestampedVersionedEntity`` that has ``id``, ``version``, ``created_on``, and ``last_modified``
attributes.

.. code:: python

    from eventsourcing.domain.model.entity import TimestampedVersionedEntity

    entity = TimestampedVersionedEntity(id=entity_id, version=1, timestamp=123)

    assert entity.id == entity_id
    assert entity.created_on == 123
    assert entity.last_modified == 123
    assert entity.version == 1


A timestamped, versioned entity is both a timestamped entity and a versioned entity.

.. code:: python

    assert isinstance(entity, TimestampedEntity)
    assert isinstance(entity, VersionedEntity)


Entity events
-------------

The library's domain entity classes have domain events defined as inner classes: ``Event``, ``Created``,
``AttributeChanged``, and ``Discarded``.

.. code:: python

    DomainEntity.Event
    DomainEntity.Created
    DomainEntity.AttributeChanged
    DomainEntity.Discarded


These inner event classes are all subclasses of ``DomainEvent`` and can be freely constructed, with
suitable arguments. ``Created`` events need an ``originator_topic`` and ``originator_id``, other
events need an ``originator_id`` and an ``originator_head``. ``AttributeChanged`` events need a
``name`` and a ``value``.

Events of versioned entities need an ``originator_version``. Events of timestamped entities
generate a ``timestamp`` when constructed for the first time.

All the events of ``DomainEntity`` generate an ``event_hash`` when constructed for the first time.
Events can be chained together by setting the ``event_hash`` of one event as the `originator_hash``
of the next event.

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
        originator_head=created.event_hash,
    )

    attribute_b_changed = VersionedEntity.AttributeChanged(
        name='b',
        value=2,
        originator_version=2,
        originator_id=entity_id,
        originator_head=attribute_a_changed.event_hash,
    )

    entity_discarded = VersionedEntity.Discarded(
        originator_version=3,
        originator_id=entity_id,
        originator_head=attribute_b_changed.event_hash,
    )


The events have a ``mutate()`` function, which can be used to mutate the
state of a given object appropriately.

For example, the ``DomainEntity.Created`` event mutates to an
entity instance. The class that is instantiated is determined by the
``originator_topic`` attribute of the ``DomainEntity.Created`` event.

.. code:: python

    entity = created.mutate()

    assert entity.id == entity_id

The ``mutate()`` method normally requires an ``obj`` argument, but
that is not required for ``DomainEntity.Created`` events. The default
is ``None``, but if a value is provided it must be callable that
returns an object, such as an object class.

As another example, when a versioned entity is mutated by an event of the
``VersionedEntity`` class, the entity version number is incremented.

.. code:: python

    assert entity.version == 1

    entity = attribute_a_changed.mutate(entity)
    assert entity.version == 2
    assert entity.a == 1

    entity = attribute_b_changed.mutate(entity)
    assert entity.version == 3
    assert entity.b == 2


Similarly, when a timestamped entity is mutated by an event of the
``TimestampedEntity`` class, the ``last_modified`` attribute of the
entity is set to have the event's ``timestamp`` value.


Data integrity
--------------

The domain events of ``DomainEntity`` are hash-chained together.

That is, the state of each event is hashed, using SHA256, and the hash of the last event
is included in the state of the next event. Before an event is applied to a entity, it
is validated in itself (the event hash represents the state of the event) and as a part of the chain
(the previous event hash equals the next event originator hash). That means, if the sequence of
events is accidentally damaged, then a ``DataIntegrityError`` will almost certainly be raised
when the sequence is replayed.

The hash of the last event applied to an aggregate root is available as an attribute called
``__head__``.

.. code:: python

    assert entity.__head__ == '9872f8ddcb62c4bd7162832393049a9ba9dec8112f8afb9e6f905db29ec484fa'

    assert entity.__head__ == attribute_b_changed.event_hash


Any change to the aggregate's sequence of events that results in a valid sequence will almost
certainly result in a different head hash. So the entire history of an aggregate can be verified
by checking the head hash. This feature could be used to protect against tampering.


Factory method
--------------

The ``DomainEntity`` has a class method ``create()`` which can return
new entity objects. When called, it constructs a ``DomainEntity.Created``
event with suitable arguments such as a unique ID, and a topic representing
the concrete entity class, and then it projects that event into an entity
object using the event's ``mutate()`` method. Then it publishes the
event, and then it returns the new entity to the caller.


.. code:: python

    entity = DomainEntity.create()
    assert entity.id
    assert entity.__class__ is DomainEntity


    entity = VersionedEntity.create()
    assert entity.id
    assert entity.version == 1
    assert entity.__class__ is VersionedEntity


    entity = TimestampedEntity.create()
    assert entity.id
    assert entity.created_on
    assert entity.last_modified
    assert entity.__class__ is TimestampedEntity


    entity = TimestampedVersionedEntity.create()
    assert entity.id
    assert entity.created_on
    assert entity.last_modified
    assert entity.version == 1
    assert entity.__class__ is TimestampedVersionedEntity



Triggering events
-----------------

Events are usually triggered by command methods of entities. Commands
will construct, apply, and publish events, using the results from working
on command arguments. The events need to be constructed with suitable arguments.

To help construct events with suitable arguments in an extensible manner, the
``DomainEntity`` class has a private method ``_trigger()``, extended by subclasses,
which can be used in command methods to construct, apply, and publish events
with suitable arguments. The event ``mutate()`` methods update the entity appropriately.

For example, triggering an ``AttributeChanged`` event on a timestamped, versioned
entity will cause the attribute value to be updated, but it will also
cause the version number to increase, and it will update the last modified time.

.. code:: python

    entity = TimestampedVersionedEntity.create()
    assert entity.version == 1
    assert entity.created_on == entity.last_modified

    # Trigger domain event.
    entity._trigger(entity.AttributeChanged, name='c', value=3)

    # Check the event was applied.
    assert entity.c == 3
    assert entity.version == 2
    assert entity.last_modified > entity.created_on


The command method ``change_attribute()`` triggers an
``AttributeChanged`` event. In the code below, the attribute ``full_name``
is triggered. A subscriber receives the event.

.. code:: python

    entity = VersionedEntity(id=entity_id, version=0)

    assert len(received_events) == 0
    subscribe(handler=receive_event, predicate=is_domain_event)

    # Apply and publish an AttributeChanged event.
    entity.change_attribute(name='full_name', value='Mr Boots')

    # Check the event was applied.
    assert entity.full_name == 'Mr Boots'

    # Check the event was published.
    assert len(received_events) == 1
    assert received_events[0].__class__ == VersionedEntity.AttributeChanged
    assert received_events[0].name == 'full_name'
    assert received_events[0].value == 'Mr Boots'

    # Check the event hash is the current entity head.
    assert received_events[0].event_hash == entity.__head__

    # Clean up.
    unsubscribe(handler=receive_event, predicate=is_domain_event)
    del received_events[:]  # received_events.clear()


Discarding entities
-------------------

The entity method ``discard()`` can be used to discard the entity, by triggering
a ``Discarded`` event, after which the entity is unavailable for further changes.

.. code:: python

    from eventsourcing.exceptions import EntityIsDiscarded

    entity.discard()

    # Fail to change an attribute after entity was discarded.
    try:
        entity.change_attribute('full_name', 'Mr Boots')
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
    user = User.create(full_name='Mrs Boots')

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
the ``change_attribute()`` method to trigger an ``AttributeChanged`` event for
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
            self.change_attribute('_password', password)

        def check_password(self, raw_password):
            password = self._encode_password(raw_password)
            return self._password == password

        def _encode_password(self, password):
            return ''.join(reversed(password))


    user = User(id='1')

    user.set_password('password')
    assert user.check_password('password')


Custom events
-------------

Custom events can be defined as inner or nested classes of the custom entity class.
In the code below, the entity class ``World`` has a custom event called ``SomethingHappened``.

Custom event classes normally extend the ``mutate()`` method, so it can affect
entities in a way that is specific to that type of event.
For example, the ``SomethingHappened`` event class extends the base ``mutate()``
method, by appending the event to the entity's ``history`` attribute.

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
            self._trigger(World.SomethingHappened, what=what_happened)

        class SomethingHappened(VersionedEntity.Event):
            """Published when something happens in the world."""
            def mutate(self, obj):
                obj = super(World.SomethingHappened, self).mutate(obj)
                obj.history.append(self)
                return obj


A new world can now be created, using the ``create()`` method. The command ``make_it_so()`` can
be used to make things happen in this world. When something happens, the history of the world
is augmented with the new event.

.. code:: python

    world = World.create()

    world.make_it_so('dinosaurs')
    world.make_it_so('trucks')
    world.make_it_so('internet')

    assert world.history[0].what == 'dinosaurs'
    assert world.history[1].what == 'trucks'
    assert world.history[2].what == 'internet'


Aggregate root
==============

The library has a domain entity class called ``AggregateRoot`` that can be useful
in a domain driven design, especially where a single command can cause many events
to be published.

The ``AggregateRoot`` entity class extends ``TimestampedVersionedEntity``. It can
be subclassed by custom aggregate root entities. In the example below, the entity
class ``World`` inherits from ``AggregateRoot``.

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
                self._trigger(World.SomethingHappened, what=something)

        class SomethingHappened(AggregateRoot.Event):
            def mutate(self, obj):
                obj = super(World.SomethingHappened, self).mutate(obj)
                obj.history.append(self)
                return obj


The ``AggregateRoot`` class overrides the ``publish()`` method of the base class,
so that triggered events are published only to a private list of pending events.

.. code:: python

    assert len(received_events) == 0
    subscribe(handler=receive_event)

    # Create new world.
    world = World.create()
    assert isinstance(world, World)

    # Command that publishes many events.
    world.make_things_so('dinosaurs', 'trucks', 'internet')

    assert world.history[0].what == 'dinosaurs'
    assert world.history[1].what == 'trucks'
    assert world.history[2].what == 'internet'


The ``AggregateRoot`` class defines a ``save()`` method, which publishes the
pending events to the publish-subscribe mechanism as a single list.

.. code:: python

    # Events are pending actual publishing until the save() method is called.
    assert len(world.__pending_events__) == 4
    assert len(received_events) == 0
    world.save()

    # Pending events were published as a single list of events.
    assert len(world.__pending_events__) == 0
    assert len(received_events) == 1
    assert len(received_events[0]) == 4

    # Clean up.
    unsubscribe(handler=receive_event)
    del received_events[:]  # received_events.clear()


Publishing all events from a single command in a single list allows all the
events to be written to a database as a single atomic operation.

That avoids the risk that some events will be stored successfully but other
events from the same command will fall into conflict and be lost, because
another thread has operated on the same  aggregate at the same time, causing
an inconsistent state that would also be difficult to repair.

It also avoids the risk of other threads picking up only some events caused
by a command, presenting the aggregate in an inconsistent or unusual and
perhaps unworkable state.
