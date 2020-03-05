==================
Domain model layer
==================

The library's domain model layer has base classes for domain events and entities. They can
be used to develop an event-sourced domain model.

.. contents:: :local:


Domain events
=============

Domain model events occur when something happens in a domain model, perhaps
recording a fact directly from the domain, or more generally registering the
results of the work of a command method (perhaps a function of facts from the
domain).

The library has a base class for domain model events called
:class:`~eventsourcing.domain.model.events.DomainEvent`.
Domain events objects can be freely constructed from this
class. Attribute values of a domain event object are set
directly from constructor keyword arguments.

.. code:: python

    from eventsourcing.domain.model.events import DomainEvent

    domain_event = DomainEvent(a=1)
    assert domain_event.a == 1


Domain events are meant to be immutable. And so the attributes of these domain
event objects are read-only: new values cannot be assigned to attributes of existing
domain event objects.

.. code:: python

    # Fail to set attribute of already-existing domain event.
    try:
        domain_event.a = 2
    except AttributeError:
        pass
    else:
        raise Exception("Shouldn't get here")


Domain events can be compared for equality and inequality. Instances
are equal if they have both the same type and the same attributes.

.. code:: python

    DomainEvent(a=1) == DomainEvent(a=1)

    DomainEvent(a=1) != DomainEvent(a=2)

    DomainEvent(a=1) != DomainEvent(b=1)


Publish-subscribe
-----------------

Domain events can be published, using the library's publish-subscribe mechanism.

The function :func:`~eventsourcing.domain.model.events.publish` is used to publish
events to subscribed handlers. The argument ``event`` is required.

.. code:: python

    from eventsourcing.domain.model.events import publish

    publish([domain_event])


The function :func:`~eventsourcing.domain.model.events.subscribe` is used to
subscribe a ``handler`` that will receive events. The optional arg ``predicate``
can be used to provide a function that will decide whether or not the subscribed
handler will actually be called when an event is published.

.. code:: python

    from eventsourcing.domain.model.events import subscribe

    received_events = []

    def receive_events(events):
        received_events.extend(events)

    def is_domain_event(events):
        return all(isinstance(e, DomainEvent) for e in events)

    subscribe(handler=receive_events, predicate=is_domain_event)

    # Publish the domain event.
    publish([domain_event])

    assert len(received_events) == 1
    assert received_events[0] == domain_event


The function :func:`~eventsourcing.domain.model.events.unsubscribe` can be
used to unsubscribe handers, to stop the handler receiving further events.

.. code:: python

    from eventsourcing.domain.model.events import unsubscribe

    unsubscribe(handler=receive_events, predicate=is_domain_event)

    # Clean up.
    del received_events[:]  # received_events.clear()


Event library
-------------

The library has a small collection of domain event subclasses, such as
:class:`~eventsourcing.domain.model.events.EventWithOriginatorID`,
:class:`~eventsourcing.domain.model.events.EventWithOriginatorVersion`,
:class:`~eventsourcing.domain.model.events.EventWithTimestamp`,
:class:`~eventsourcing.domain.model.events.EventWithTimeuuid`,
:class:`~eventsourcing.domain.model.events.EventWithHash`,
:class:`~eventsourcing.domain.model.events.CreatedEvent`,
:class:`~eventsourcing.domain.model.events.AttributeChangedEvent`, and
:class:`~eventsourcing.domain.model.events.DiscardedEvent`.

Some classes require particular arguments when constructed. An ``originator_id`` arg
is required for :class:`~eventsourcing.domain.model.events.EventWithOriginatorID`
to identify a sequence to which the event belongs. An ``originator_version`` arg is
required for :class:`~eventsourcing.domain.model.events.EventWithOriginatorVersion`
to position the events in a sequence.

.. code:: python

    from eventsourcing.domain.model.events import EventWithOriginatorID
    from eventsourcing.domain.model.events import EventWithOriginatorVersion
    from uuid import uuid4

    # Requires originator_id.
    EventWithOriginatorID(originator_id=uuid4())

    # Requires originator_version.
    EventWithOriginatorVersion(originator_version=0)


Some of these classes provide useful defaults for particular attributes, such as the ``timestamp``
of an :class:`~eventsourcing.domain.model.events.EventWithTimestamp` (a ``Decimal`` value) and
the ``event_id`` (a version 1 ``UUID``) of an
:class:`~eventsourcing.domain.model.events.EventWithTimeuuid`.

.. code:: python

    from eventsourcing.domain.model.events import EventWithTimestamp
    from eventsourcing.domain.model.events import EventWithTimeuuid
    from decimal import Decimal
    from uuid import UUID

    assert isinstance(EventWithTimestamp().timestamp, Decimal)

    assert isinstance(EventWithTimeuuid().event_id, UUID)


The event classes are useful for their distinct type, for example in subscription predicates.

.. code:: python

    from eventsourcing.domain.model.events import (
        CreatedEvent, AttributeChangedEvent, DiscardedEvent
    )

    def is_created(event):
        return isinstance(event, CreatedEvent)


    def is_attribute_changed(event):
        return isinstance(event, AttributeChangedEvent)


    def is_discarded(event):
        return isinstance(event, DiscardedEvent)


    assert is_created(CreatedEvent()) is True
    assert is_discarded(CreatedEvent()) is False

    assert is_created(DiscardedEvent()) is False
    assert is_discarded(DiscardedEvent()) is True

    assert is_created(DomainEvent()) is False
    assert is_discarded(DomainEvent()) is False


Custom events
-------------

Custom domain events can be coded by subclassing the library's domain event classes.

Domain events are normally named using the past participle of a common verb, for example
a regular past participle such as "started", "paused", "stopped", or an irregular past
participle such as "chosen", "done", "found", "paid", "quit", "seen".

.. code:: python

    class SomethingHappened(DomainEvent):
        """
        Triggered whenever something happens.
        """


It is possible to code domain events as inner or nested classes.

.. code:: python

    class Job(object):

        class Seen(EventWithTimestamp):
            """
            Triggered when the job is seen.
            """

        class Done(EventWithTimestamp):
            """
            Triggered when the job is done.
            """

Inner or nested classes can be used, and are used in the library, to define
the domain events of a domain entity on the entity class itself.

.. code:: python

    seen = Job.Seen(job_id='#1')
    done = Job.Done(job_id='#1')

    assert done.timestamp > seen.timestamp


Deleting events
---------------

The general rule is never to delete events.

However, a perfectly adequate solution to storing and deleting personally identifiable
information (for example to comply with data protection regulations such as GDPR)
is to record encrypted stored events that are not notifiable (and so won't appear in
the notification log of an application, and so won't be propagated) and delete these
event records when the information need to be deleted. Each instance attribute could
be stored as a separate aggregate, or there could be one aggregate holding all the PII
for one individual. Store these events atomically with the events that would otherwise
include the events. Consider using UUIDv5 to generated UUIDs for these aggregates.

Use the ``get_records()`` and ``delete_record()`` methods of a record manager to
delete the records of for an aggregate (see record manager documentation for details).


Domain entities
===============

A domain entity is an object that has an identity which provides
a thread of continuity. The attributes of a domain entity can change,
directly by assignment, or indirectly by calling a method of the object.
But the identity does not change.

The library has a base class for domain entities called
:class:`~eventsourcing.domain.model.entity.DomainEntity`.
It has an ``id`` attribute, because all entities are
meant to have a constant ID that provides continuity when
other attributes change.

In the example below, a domain entity object is constructed
with an ID that is a version 4 UUID.

.. code:: python

    from eventsourcing.domain.model.entity import DomainEntity

    entity_id = uuid4()

    entity = DomainEntity(id=entity_id)

    assert entity.id == entity_id


Entity library
--------------

The library also has a domain entity class called
:class:`~eventsourcing.domain.model.entity.VersionedEntity`,
which extends the :class:`~eventsourcing.domain.model.entity.DomainEntity`
class with a ``__version__`` attribute.

.. code:: python

    from eventsourcing.domain.model.entity import VersionedEntity

    entity = VersionedEntity(id=entity_id, __version__=1)

    assert entity.id == entity_id
    assert entity.__version__ == 1


The library also has a domain entity class called
:class:`~eventsourcing.domain.model.entity.TimestampedEntity`,
which extends the :class:`~eventsourcing.domain.model.entity.DomainEntity`
class with attributes ``__created_on__`` and ``__last_modified__``.

.. code:: python

    from eventsourcing.domain.model.entity import TimestampedEntity

    entity = TimestampedEntity(id=entity_id, __created_on__=123)

    assert entity.id == entity_id
    assert entity.__created_on__ == 123
    assert entity.__last_modified__ == 123


There is also a
:class:`~eventsourcing.domain.model.entity.TimestampedVersionedEntity`,
that has ``id``, ``__version__``, ``__created_on__``, and ``__last_modified__``
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
which is assumed to be required by all domain entities (and aggregates) in
all domains.


Entity events
-------------

The library's domain entity classes have domain events defined as inner
classes:
:class:`~eventsourcing.domain.model.entity.DomainEntity.Event`,
:class:`~eventsourcing.domain.model.entity.DomainEntity.Created`,
:class:`~eventsourcing.domain.model.entity.DomainEntity.AttributeChanged`,
:class:`~eventsourcing.domain.model.entity.DomainEntity.Discarded`.


.. code:: python

    DomainEntity.Event
    DomainEntity.Created
    DomainEntity.AttributeChanged
    DomainEntity.Discarded


The domain event class :class:`~eventsourcing.domain.model.entity.DomainEntity.Event`
is inherited by the others. The others also inherit from the corresponding library
base classes
:class:`~eventsourcing.domain.model.events.Created`,
:class:`~eventsourcing.domain.model.events.AttributeChanged`, and
:class:`~eventsourcing.domain.model.events.Discarded`.

The domain entity's event class :class:`~eventsourcing.domain.model.entity.DomainEntity.Event`
inherits from the base domain event class :class:`~eventsourcing.domain.model.events.DomainEvent`
and from :class:`~eventsourcing.domain.model.events.EventWithOriginatorID` so that all
events of :class:`~eventsourcing.domain.model.entity.DomainEntity`
have an ``originator_id`` attribute.


.. code:: python

    assert issubclass(DomainEntity.Created, DomainEntity.Event)
    assert issubclass(DomainEntity.AttributeChanged, DomainEntity.Event)
    assert issubclass(DomainEntity.Discarded, DomainEntity.Event)

    assert issubclass(DomainEntity.Created, CreatedEvent)
    assert issubclass(DomainEntity.AttributeChanged, AttributeChangedEvent)
    assert issubclass(DomainEntity.Discarded, DiscardedEvent)

    assert issubclass(DomainEntity.Event, DomainEvent)


These entity event classes can be freely constructed, with suitable arguments.

All events of :class:`~eventsourcing.domain.model.entity.DomainEntity`
need an ``originator_id``.
:class:`~eventsourcing.domain.model.entity.DomainEntity.Created` events
also need an ``originator_topic``.
:class:`~eventsourcing.domain.model.entity.DomainEntity.AttributeChanged` events
also need ``name`` and ``value``.

Events of :class:`~eventsourcing.domain.model.entity.VersionedEntity`
also need an ``originator_version``. Events of
:class:`~eventsourcing.domain.model.entity.TimestampedEntity`
generate a current ``timestamp`` value, unless one is given.


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


All the events have a
:func:`~eventsourcing.domain.model.events.DomainEvent.__mutate__` method, which
can be used to mutate the state of an entity. This is a convenient way to code the
"default" or "self" projection of the entity's sequence of events (the projection
of the events into the entity itself).

For example, the
:func:`~eventsourcing.domain.model.entity.DomainEntity.Created.__mutate__` method
of an entity's :class:`~eventsourcing.domain.model.entity.DomainEntity.Created`
event mutates "nothing" to an entity instance. The class that is instantiated is
determined by the event's ``originator_topic`` attribute. Although the
:func:`~eventsourcing.domain.model.events.DomainEvent.__mutate__` method of an
event normally requires a value to be given for the ``obj`` argument, it is
optional for the method on
:class:`~eventsourcing.domain.model.entity.DomainEntity.Created` events. If a
value is provided it must be a callable that returns an entity when called,
such as a domain entity class. If a domain entity class is given as the ``obj``
arg, then the event's ``originator_topic`` will be ignored for the purposes of
determining which class to instantiate.

.. code:: python

    entity = created.__mutate__(None)

    assert entity.id == entity_id


When a :class:`~eventsourcing.domain.model.entity.VersionedEntity` is mutated by
one of its domain events, the entity version number is set to the event's
``originator_version``.

.. code:: python

    assert entity.__version__ == 0

    entity = attribute_a_changed.__mutate__(entity)
    assert entity.__version__ == 1
    assert entity.a == 1

    entity = attribute_b_changed.__mutate__(entity)
    assert entity.__version__ == 2
    assert entity.b == 2


Similarly, when a :class:`~eventsourcing.domain.model.entity.TimestampedEntity`
is mutated by one of its events, the ``__last_modified__`` attribute of the
entity is set to the event's ``timestamp`` value.


Hash-chained events
-------------------

The library also has entity class
:class:`~eventsourcing.domain.model.entity.EntityWithHashchain`.
It has event classes that inherit from
:class:`~eventsourcing.domain.model.events.EventWithHash`.

.. code:: python

    from eventsourcing.domain.model.entity import EntityWithHashchain
    from eventsourcing.domain.model.events import EventWithHash


    assert issubclass(EntityWithHashchain.Event, EventWithHash)
    assert issubclass(EntityWithHashchain.Created, EventWithHash)
    assert issubclass(EntityWithHashchain.AttributeChanged, EventWithHash)
    assert issubclass(EntityWithHashchain.Discarded, EventWithHash)


All the events of
:class:`~eventsourcing.domain.model.entity.EntityWithHashchain`
use SHA-256 to generate an ``event_hash``
from the event attribute values when constructed for the first time. Events
are chained together by :class:`~eventsourcing.domain.model.entity.EntityWithHashchain`
by constructing each subsequent event to have an attribute ``__previous_hash__``
which is the ``__event_hash__`` of the previous event (stored by the entity on
entity's ``__head__`` attribute).


Factory method
--------------

The :class:`~eventsourcing.domain.model.entity.DomainEntity` has a class
method :func:`~eventsourcing.domain.model.entity.DomainEntity.__create__`
which returns new entities. When called, it constructs a
:class:`~eventsourcing.domain.model.entity.DomainEntity.Created` event
with suitable arguments such as a unique ID, and a topic representing the
concrete entity class, and then it projects that event into an entity object
using the event's :func:`~eventsourcing.domain.model.entity.DomainEntity.Created.__mutate__`
method. Then it publishes the event, and then it returns the new entity to the caller.
This technique works correctly for subclasses of both the entity and the event class.

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

To help trigger events in an extensible manner, the
:class:`~eventsourcing.domain.model.entity.DomainEntity` class has a
method called
:class:`~eventsourcing.domain.model.entity.DomainEntity.__trigger_event__()`,
that is extended by subclasses in the library.
It can be used in command  methods to construct, apply, and publish events with
suitable arguments.

For example, triggering an :class:`~eventsourcing.domain.model.events.AttributeChangedEvent`
on a timestamped, versioned entity will cause the attribute value to be updated,
but it will also cause the version number to increase, and it will update the last
modified time.

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


Changing attributes
-------------------

The command method
:func:`~eventsourcing.domain.model.entity.DomainEntity.__change_attribute__`
triggers an :class:`~eventsourcing.domain.model.entity.DomainEntity.AttributeChanged`
event. In the code below, the attribute ``full_name``
is set to 'Mr Boots'. A subscriber receives the event.

.. code:: python

    subscribe(handler=receive_events, predicate=is_domain_event)
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
    unsubscribe(handler=receive_events, predicate=is_domain_event)
    del received_events[:]  # received_events.clear()


Discarding entities
-------------------

The command method
:func:`~eventsourcing.domain.model.entity.DomainEntity.__discard__()` triggers a
:class:`~eventsourcing.domain.model.entity.DomainEntity.Discarded` event, after which
the entity is unavailable for further changes.

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

The library function
:func:`~eventsourcing.domain.model.decorators.attribute`
is a decorator that provides a property getter and setter. It
will trigger an
:class:`~eventsourcing.domain.model.entity.DomainEntity.AttributeChanged`
event when a value is assigned to the property. Simple mutable attributes
can be coded as decorated functions without a body (any body is ignored)
such as ``full_name`` of ``User`` below .

.. code:: python

    from eventsourcing.domain.model.decorators import attribute


    class User(VersionedEntity):

        def __init__(self, full_name, *args, **kwargs):
            super(User, self).__init__(*args, **kwargs)
            self._full_name = full_name

        @attribute
        def full_name(self):
            """
            The full name of the user (an event-sourced attribute).
            """


In the code below, after the entity has been created, assigning to ``full_name`` triggers
an :class:`~eventsourcing.domain.model.entity.VersionedEntity.AttributeChanged`. A
:class:`~eventsourcing.domain.model.entity.VersionedEntity.Created` event and an
:class:`~eventsourcing.domain.model.entity.VersionedEntity.AttributeChanged`
event are received by a subscriber.

.. code:: python

    assert len(received_events) == 0
    subscribe(handler=receive_events, predicate=is_domain_event)

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
    unsubscribe(handler=receive_events, predicate=is_domain_event)
    del received_events[:]  # received_events.clear()


Custom commands
---------------

The entity base classes can be extended with custom command methods. In general,
the arguments of a command will be used to perform some work. Then, the result
of the work will be used to trigger a domain event that represents what happened.
Please note, command methods normally have no return value.

For example, the ``set_password()`` method of the ``User`` entity below is given a
raw password. It creates an encoded string from the raw password, and then uses the
:func:`~eventsourcing.domain.model.entity.DomainEntity.__change_attribute__` method
to trigger an
:class:`~eventsourcing.domain.model.entity.VersionedEntity.AttributeChanged`
event for the ``_password`` attribute, with the encoded password as the new
value of the attribute.

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

Custom event classes can extend the
:func:`~eventsourcing.domain.model.events.DomainEvent.__mutate__` method, so it affects
entities in a way that is specific to that type of event. More conveniently, event
classes can implement a :func:`~eventsourcing.domain.model.events.DomainEvent.mutate`
method, which avoids the need to call the super method and return the ``obj``. For example,
the event class ``SomethingHappened`` has a ``mutate()`` method which simply appends the
``what`` of the event to the entity's ``history``.

Custom events are normally triggered by custom commands. In the example below,
the command method ``make_it_so()`` triggers the custom event ``SomethingHappened``.

.. code:: python

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
            """Triggered when something happens in the world."""
            def mutate(self, obj):
                obj.history.append(self.what)


A new "world" entity can now be created, using the class method
:func:`~eventsourcing.domain.model.entity.DomainEntity.__create__`.
The entity command ``make_it_so()`` can be used to make things
happen in this world. When something happens, the history of the world
is augmented with the new event.

.. code:: python

    world = World.__create__()

    world.make_it_so('dinosaurs')
    world.make_it_so('trucks')
    world.make_it_so('internet')

    assert world.history[0] == 'dinosaurs'
    assert world.history[1] == 'trucks'
    assert world.history[2] == 'internet'


Auto-subclassing events
-----------------------

In order to distinguish between events of different entity classes that inherit their
events from a common entity base class, it is necessary to subclass the event classes
on each of the entity classes.

Without subclassing the domain events of an inherited entity class, the custom
entity classes will have exactly the same domain event classes.

.. code:: python

    class Example1(DomainEntity):
        pass


    class Example2(DomainEntity):
        pass


    assert Example1.Event == Example2.Event
    assert Example1.Created  == Example2.Created
    assert Example1.Discarded  == Example2.Discarded
    assert Example1.AttributeChanged  == Example2.AttributeChanged


With subclassing the domain events of an inherited entity class, the custom
entity classes will have distinct domain event classes.

.. code:: python

    class Example3(DomainEntity):
        class Event(DomainEntity.Event): pass
        class Created(Event, DomainEntity.Created): pass
        class Discarded(Event, DomainEntity.Discarded): pass
        class AttributeChanged(Event, DomainEntity.AttributeChanged): pass
        class SomethingHappened(Event): pass


    class Example4(DomainEntity):
        class Event(DomainEntity.Event): pass
        class Created(Event, DomainEntity.Created): pass
        class Discarded(Event, DomainEntity.Discarded): pass
        class AttributeChanged(Event, DomainEntity.AttributeChanged): pass
        class SomethingHappened(Event): pass


    assert Example3.Event != Example4.Event
    assert Example3.Created != Example4.Created
    assert Example3.Discarded != Example4.Discarded
    assert Example3.AttributeChanged != Example4.AttributeChanged


Some people will like to make explict the event subclasses. However, some people
will find this cumbersome "boilerplate".

To avoid the appearance of "boilerplate", it is possible to achieve exactly the
same distinct event subclasses, as above, by decorating the entity class with the
``@subclassevents`` decorator. In this case, custom events need only to inherit
from the base ``DomainEvent`` class, and will then be subclassed automatically
as an ``Event`` of the custom entity class (which will be defined first, if missing).

.. code:: python

    from eventsourcing.domain.model.decorators import subclassevents


    @subclassevents
    class Example5(DomainEntity):
        class SomethingHappened(DomainEvent):
            pass


    @subclassevents
    class Example6(DomainEntity):
        class SomethingHappened(DomainEvent):
            pass


    assert Example5.Event != Example6.Event
    assert Example5.Created != Example6.Created
    assert Example5.Discarded != Example6.Discarded
    assert Example5.AttributeChanged != Example6.AttributeChanged

    assert issubclass(Example5.SomethingHappened, Example5.Event)
    assert issubclass(Example6.SomethingHappened, Example6.Event)


To avoid having to use the decorator on all of the custom entity
classes in a model, which may itself start to feel like "boilerplate",
it is possible to set ``__subclassevents__`` on a common custom base
entity class.

.. code:: python

    class BaseEntity(DomainEntity):
        __subclassevents__ = True


    class Example5(BaseEntity):
        class SomethingHappened(DomainEvent):
            pass


    class Example6(BaseEntity):
        class SomethingHappened(DomainEvent):
            pass


    assert Example5.Event != Example6.Event
    assert Example5.Created != Example6.Created
    assert Example5.Discarded != Example6.Discarded
    assert Example5.AttributeChanged != Example6.AttributeChanged

    assert issubclass(Example5.SomethingHappened, Example5.Event)
    assert issubclass(Example6.SomethingHappened, Example6.Event)


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

Base class
----------

The library has a domain entity class called
:class:`~eventsourcing.domain.model.aggregate.BaseAggregateRoot` that can be
useful in a domain driven design, especially where a single command can cause
many events to be published. The :class:`~eventsourcing.domain.model.aggregate.BaseAggregateRoot`
entity class extends :class:`~eventsourcing.domain.model.entity.TimestampedVersionedEntity`.
Its method :func:`~eventsourcing.domain.model.aggregate.BaseAggregateRoot.__publish__` overrides
the base class :class:`~eventsourcing.domain.model.entity.DomainEntity`, so that triggered events
are published only to a private list of pending events, rather than directly to the publish-subscribe
mechanism. It also introduces the method
:func:`~eventsourcing.domain.model.aggregate.BaseAggregateRoot.__save__`, which publishes all
pending events to the publish-subscribe mechanism as a single list.

It can be subclassed by custom aggregate root entities. In the example below, the
entity class ``World`` inherits from :class:`~eventsourcing.domain.model.aggregate.BaseAggregateRoot`.

.. code:: python

    from eventsourcing.domain.model.aggregate import BaseAggregateRoot


    class World(BaseAggregateRoot):
        """
        Example domain entity, with mutator function on domain event.
        """
        def __init__(self, *args, **kwargs):
            super(World, self).__init__(*args, **kwargs)
            self.history = []

        def make_things_so(self, *somethings):
            for something in somethings:
                self.__trigger_event__(World.SomethingHappened, what=something)

        class SomethingHappened(BaseAggregateRoot.Event):
            def mutate(self, obj):
                obj.history.append(self.what)


The ``World`` aggregate root has a command method ``make_things_so()`` which publishes
``SomethingHappened`` events. The ``mutate()`` method of the ``SomethingHappened`` class
simply appends the event (``self``) to the aggregate object (``obj``).

We can see the events that are published by subscribing to the handler ``receive_events()``.

.. code:: python

    assert len(received_events) == 0
    subscribe(handler=receive_events)

    # Create new world.
    world = World.__create__()
    assert isinstance(world, World)

    # Command that publishes many events.
    world.make_things_so('dinosaurs', 'trucks', 'internet')

    # State of aggregate object has changed
    # but no events have been published yet.
    assert len(received_events) == 0
    assert world.history[0] == 'dinosaurs'
    assert world.history[1] == 'trucks'
    assert world.history[2] == 'internet'


Events are pending, and will not be published until
:func:`~eventsourcing.domain.model.aggregate.BaseAggregateRoot.__save__` is called.

.. code:: python

    # Has pending events.
    assert len(world.__pending_events__) == 4

    # Publish pending events.
    world.__save__()

    # Pending events published as a list.
    assert len(received_events) == 4

    # No longer any pending events.
    assert len(world.__pending_events__) == 0


Data integrity
--------------

The library class
:class:`~eventsourcing.domain.model.aggregate.AggregateRootWithHashchainedEvents`
extends
:class:`~eventsourcing.domain.model.aggregate.BaseAggregateRoot` by also inheriting from
:class:`~eventsourcing.domain.model.entity.EntityWithHashchain`, so
that aggregate events are individually hashed and also hash-chained together.
It is "aliased" as :class:`~eventsourcing.domain.model.aggregate.AggregateRoot`.

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
                obj.history.append(self.what)


    # Create new world.
    world = World.__create__()
    assert isinstance(world, World)

    # Command that publishes many events.
    world.make_things_so('dinosaurs', 'trucks', 'internet')

    # State of aggregate object has changed
    # but no events have been published yet.
    assert world.history[0] == 'dinosaurs'
    assert world.history[1] == 'trucks'
    assert world.history[2] == 'internet'

    # Publish pending events.
    world.__save__()

The state of each event, including the hash of the previous event, is hashed using
SHA-256. The state of each event can be validated as a part of the chain. If the
sequence of events is accidentally damaged in any way, then a
:class:`~eventsourcing.exceptions.DataIntegrityError`
will almost certainly be raised from the domain layer when the sequence is replayed.

The hash of the last event applied to an aggregate root is available as an attribute called
``__head__`` of the aggregate root.

.. code:: python

    # Entity's head hash is determined exclusively
    # by the entire sequence of events and SHA-256.
    assert world.__head__ == received_events[-1].__event_hash__


A different sequence of events will almost certainly result a different
head hash. So the entire history of an entity can be verified by checking the
head hash against an independent record.

The hashes can be salted by setting environment variable ``SALT_FOR_DATA_INTEGRITY``,
perhaps with random bytes encoded as Base64.

.. code:: python

    from eventsourcing.utils.random import encoded_random_bytes

    # Keep this safe.
    salt = encoded_random_bytes(num_bytes=32)

    # Configure environment (before importing library).
    import os
    os.environ['SALT_FOR_DATA_INTEGRITY'] = salt


The "genesis hash" used as the previous hash of the first event in a sequence can be
set using environment variable ``GENESIS_HASH``.

The class
:class:`~eventsourcing.domain.model.aggregate.AggregateRootWithHashchainedEvents`
can be used when you want to be able to verify aggregates' sequences of events
cryptographically (which can be useful even during development to catch programming
errors and to avoid doubt that the infrastructure is working properly). However, the
class :class:`~eventsourcing.domain.model.aggregate.BaseAggregateRoot`
is probably faster and can be used whenever you don't actually need to verify
the sequence of events cryptographically.

.. code:: python

    # Clean up after running examples.
    unsubscribe(handler=receive_events)
    del received_events[:]  # received_events.clear()


Versioning
==========

The library class :class:`~eventsourcing.domain.model.versioning.Upcastable`
supports versioning. This class is inherited by all of the domain event
classes in the library, so that custom event classes can be versioned. It
is also inherited by the domain entity classes, so that custom entity
classes can be versioned (snapshots can be upcast).


Versioning events
-----------------

As changes are made to an event class, the class attribute ``__class_version__``
can be incremented through a series of integer values. If the ``__class_version__``
is a non-zero value, it will be included in the recorded states of all instances of
the event class. The original value is ``0`` and so the first time this attribute
is set on a custom event class, the attribute should be set to ``1``.

If the event class attribute ``__class_version__`` has a non-zero value,
when the event class method :func:`~eventsourcing.domain.model.versioning.Upcastable.__upcast_state__`
is called, the event class method
:func:`~eventsourcing.domain.model.versioning.Upcastable.__upcast__`
will be called successively, once for each version, starting from the version of
the stored event state, until the current version is reached.

By default, :func:`~eventsourcing.domain.model.versioning.Upcastable.__upcast__`
raises a ``NotImplementedError`` exception. And so if the ``__class_version__``
of a custom event class has a non-zero value, then this method will need to be
overridden on the custom event class, and implemented to support upcasting from
the original version ``0`` to version ``1``. The next time the event class is changed,
the class version number will need to be set to ``2``, and the custom ``__upcast__()``
method amended so that it supports both upcasting from version ``0`` to version ``1``
and additionally from version ``1`` to version ``2``. And so on.

.. code:: python

    from copy import copy

    # Original version.
    class ExampleEvent(DomainEvent):
        pass

    # Construct state with original version of the event class.
    state_v0 = ExampleEvent(a=1).__dict__
    assert state_v0["a"] == 1

    # Check version 1 is correctly upcast to version 1.
    state_v0_from_v0 = ExampleEvent.__upcast_state__(copy(state_v0))
    assert state_v0_from_v0["a"] == 1

    # Version 1 (has attribute 'b').
    class ExampleEvent(DomainEvent):
        __class_version__ = 1

        @classmethod
        def __upcast__(cls, obj_state, class_version):
            if class_version == 0:
                # Supply default for 'b'.
                obj_state['b'] = 0
            return obj_state

    # Construct state with version 1 of the event class.
    state_v1 = ExampleEvent(a=1, b=2).__dict__
    assert state_v1["a"] == 1
    assert state_v1["b"] == 2

    # Check original version is correctly upcast to version 1.
    state_v1_from_v0 = ExampleEvent.__upcast_state__(copy(state_v0))
    assert state_v1_from_v0["a"] == 1
    assert state_v1_from_v0["b"] == 0  # gets default value

    # Check version 1 is correctly upcast to version 1.
    state_v1_from_v1 = ExampleEvent.__upcast_state__(copy(state_v1))
    assert state_v1_from_v1["a"] == 1
    assert state_v1_from_v1["b"] == 2

    # Version 2 (has attribute 'c').
    class ExampleEvent(DomainEvent):
        __class_version__ = 2

        @classmethod
        def __upcast__(cls, obj_state, class_version):
            if class_version == 0:
                # Supply default for 'b'.
                obj_state['b'] = 0
            elif class_version == 1:
                # Supply default for 'c'.
                obj_state['c'] = ''
            return obj_state

    # Construct state with version 2 of the event class.
    state_v2 = ExampleEvent(a=1, b=2, c='c').__dict__
    assert state_v2["a"] == 1
    assert state_v2["b"] == 2

    # Check original version is correctly upcast to version 2.
    state_v2_from_v0 = ExampleEvent.__upcast_state__(copy(state_v0))
    assert state_v2_from_v0["a"] == 1
    assert state_v2_from_v0["b"] == 0  # gets default value
    assert state_v2_from_v0["c"] == ''  # gets default value

    # Check version 1 is correctly upcast to version 2.
    state_v2_from_v1 = ExampleEvent.__upcast_state__(copy(state_v1))
    assert state_v2_from_v1["a"] == 1
    assert state_v2_from_v1["b"] == 2
    assert state_v2_from_v1["c"] == ''  # gets default value

    # Check version 2 is correctly upcast to version 2.
    state_v2_from_v2 = ExampleEvent.__upcast_state__(copy(state_v2))
    assert state_v2_from_v2["a"] == 1
    assert state_v2_from_v2["b"] == 2
    assert state_v2_from_v2["c"] == 'c'


Please refer to the :class:`~eventsourcing.domain.model.versioning.Upcastable`
documentation for more information about versioning events, especially about
restrictions involved when providing for forward compatibility, and when you
might need to do that.


Versioning entities
-------------------

When reconstructing domain entities from stored event records, for example when
retrieving aggregates from an application repository, the sequenced item mapper
calls the library function
:func:`~eventsourcing.utils.topic.reconstruct_object`
which calls the event class method
:func:`~eventsourcing.domain.model.versioning.Upcastable.__upcast_state__`,
as above. This is the only place in the library where
:func:`~eventsourcing.domain.model.versioning.Upcastable.__upcast_state__`
is called.

Care needs to be taken when using both snapshotting and versioning,
since differences introduced by newer versions of events, and changes
to an entity class since a snapshot was made might not exist in the snapshot,
and that might matter.

One option is to delete snapshots created by a previous version of the class.
New snapshots will need to be made. Suddenly stopping use of old snapshots,
and so replaying all the stored events to create a new snapshot, would briefly
degrade performance to the extent it was improved by using snapshots.

Another option is upcasting the snapshotted state.
The domain entity classes are also ``Upcastable`` classes, and so it is possible
to override the ``__upcast__()`` method on the entity class, which will be called
when reconstructing an entity from a snapshot. The body of this implementation
needs to manipulate state of the snapshot to conform with the state that would
be obtained by reconstructing using the upgraded event versions. This can help
in simple cases, but there may cases where the correct state cannot be obtained
in this way. The class attribute ``__class_version__`` is used to define the version
of the entity class (with integer version numbers 1, 2, etc).

The example below shows a custom domain entity class, which upcasts snapshotted state
by adding default values for 'value' and 'units'. This class gestures towards having
been defined originally without either attribute. It is supposed that version 1
added the 'value' attribute, and the 'units' attribute was added in version 2.

A snapshot of the state of an original version of the entity wouldn't have 'value',
and so upcasting from the original version to version 1 involves defining 'value'.
A snapshot of the state of version 1 of the entity woud have 'value' but wouldn't
have 'units', and so upcasting from version 1 to version 2 involves defining
'units'.

.. code:: python

    class ExampleAggregate(BaseAggregateRoot):
        __class_version__ = 2

        DEFAULT_VALUE = 0
        DEFAULT_UNITS = ""

        def __init__(self, **kwargs):
            self.value = self.DEFAULT_VALUE  # added in version 1
            self.units = self.DEFAULT_UNITS  # added in version 2

        @classmethod
        def __upcast__(cls, obj_state, class_version):
            if class_version == 0:
                # Upcast to version 1.
                obj_state['value'] = cls.DEFAULT_VALUE
            elif class_version == 1:
                # Upcast to version 2.
                obj_state['units'] = cls.DEFAULT_UNITS
            return obj_state


Copy and replace
----------------

Copy-and-replace is an alternative to upcasting.
It is possible to accumulate so many changes that it becomes desirable
to replace the old versions of stored events with new versions.
