============
Domain Model
============

The library's domain layer complements the infrastructure layer by providing some domain driven design shaped objects
that work with cohesive mechanism for storing domain events as sequences of items.

The domain layer contains object classes for: domain events, domain entities, aggregate roots, and entity repositories.


Events
======

The purpose of a domain event is to be instantiated and published when something happens, such as the results from the
work of a command.

The library's base class for domain events is ``DomainEvent``. Domain event object instances can be freely constructed
from the ``DomainEvent`` object class. Event attributes are set directly from constructor keyword arguments.

.. code:: python

    from eventsourcing.domain.model.events import DomainEvent

    domain_event = DomainEvent(a=1)

    assert domain_event.a == 1


The attributes of a domain event object are read-only, new values cannot be assigned to existing domain
event objects. Domain event objects are immutable in that sense.

.. code:: python

    # Fail to assign a new value to a domain event.
    try:
        domain_event.a = 2
    except AttributeError:
        pass
    else:
        raise Exception("Shouldn't get here")


Domain events can be compared for equality and inequality as value objects (instances are equal if they have the
same type and the same attributes).

.. code:: python

    DomainEvent(a=1) == DomainEvent(a=1)

    DomainEvent(a=1) != DomainEvent(a=2)

    DomainEvent(a=1) != DomainEvent(b=1)


Domain events can be published, using the library's publish-subscribe mechanism. The ``publish()`` function is used to
publish events. The ``event`` arg is required.

.. code:: python

    from eventsourcing.domain.model.events import publish

    publish(event=domain_event)


The ``subscribe()`` function is used to subscribe a ``handler`` to events. The optional ``predicate`` arg can
be used to provide a function that will decide whether or not the subscribed handler will be called
when an event is published.


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


The ``unsubscribe()`` function can be used to cancel a subscription.

.. code:: python

    from eventsourcing.domain.model.events import unsubscribe

    unsubscribe(handler=receive_event, predicate=is_domain_event)

    received_events.clear()


Event Library
-------------

The library has a rich collection of domain event subclasses, such as ``EventWithOriginatorID``,
``EventWithOriginatorVersion``, ``EventWithTimestamp``, ``EventWithTimeuuid``, ``Created``, ``AttributeChanged``,
``Discarded``.

Some of these classes provide useful default values for particular attributes, such as a timestamp.

.. code:: python

    from eventsourcing.domain.model.events import EventWithTimestamp
    from eventsourcing.domain.model.events import EventWithTimeuuid
    from uuid import UUID

    # Automatic timestamp.
    assert isinstance(EventWithTimestamp().timestamp, float)

    # Automatic UUIDv1.
    assert isinstance(EventWithTimeuuid().event_id, UUID)


Some classes require particular attributes when constructed.

.. code:: python

    from eventsourcing.domain.model.events import EventWithOriginatorVersion
    from eventsourcing.domain.model.events import EventWithOriginatorID
    from uuid import uuid4

    # Requires originator_id.
    EventWithOriginatorID(originator_id=uuid4())

    # Requires originator_version.
    EventWithOriginatorVersion(originator_version=0)


Some classes are just useful for their distinct type, for example in subscription predicates.

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


Custom Events
-------------

You can code for your own domain events, by subclassing the library's domain event classes. When deciding names for
your domain events, try to use the past participle of a common verb. For example, a regular verb like "started",
"paused", "stopped", or an irregular verb such as "chosen", "done", "found", "paid", "quit", "seen".

.. code:: python

    class SomethingHappened(DomainEvent):
        """
        Published whenever something happens.
        """


It is possible to code domain events as inner or nested classes.

.. code:: python

    class Job(object):

        class Started(EventWithTimestamp):
            """
            Published when the job is started.
            """

        class Done(EventWithTimestamp):
            """
            Published when the job is done.
            """


    started_event = Job.Started(job_id='#1')
    done_event = Job.Done(job_id='#1')

    assert started_event.timestamp < done_event.timestamp


Inner or nested classes can be used, and are used in the library, to define the domain events of a domain entity
on the domain entity class itself (see below).


Entities
========

A domain entity is an object that is not defined by its attributes, but rather by a thread of continuity and its
identity.

The attributes of a domain entity can change, directly by assignment, or indirectly by calling a method of the object.

The library provides a domain entity class ``VersionedEntity``, which has an ``id`` attribute, and a ``version``
attribute.

.. code:: python

    from eventsourcing.domain.model.entity import VersionedEntity

    entity_id = uuid4()

    entity = VersionedEntity(id=entity_id, version=0)

    assert entity.id == entity_id
    assert entity.version == 0


There is a ``TimestampedEntity`` that has ``id`` and ``created_on`` attributes. It also has a ``last_modified``
attribute which is normally updated as events are applied.

.. code:: python

    from eventsourcing.domain.model.entity import TimestampedEntity

    entity_id = uuid4()

    entity = TimestampedEntity(id=entity_id, timestamp=123456789)

    assert entity.id == entity_id
    assert entity.created_on == 123456789
    assert entity.last_modified == 123456789


There is also a ``TimestampedVersionedEntity`` that has ``id``, ``version``, ``created_on``, and ``last_modified``
attributes.

.. code:: python

    from eventsourcing.domain.model.entity import TimestampedVersionedEntity

    entity_id = uuid4()

    entity = TimestampedVersionedEntity(id=entity_id, version=0, timestamp=123456789)

    assert entity.id == entity_id
    assert entity.version == 0
    assert entity.created_on == 123456789
    assert entity.last_modified == 123456789


The base class ``DomainEntity`` has a method ``_increment_version()`` which can be used to increment the version number
 of an entity.

.. code:: python

    entity._increment_version()

    assert entity.version == 1


The library's domain entity classes have inner domain event classes: ``Event``, ```Created``, ``AttributeChanged``, and
``Discarded``. These inner event classes are all subclasses of ``DomainEvent`` and can be freely constructed, with
suitable arguments.

.. code:: python

    entity_created = VersionedEntity.Created(
        originator_version=0,
        originator_id=entity_id,
    )

    entity_attribute_a_changed = VersionedEntity.AttributeChanged(
        name='a',
        value=1,
        originator_version=1,
        originator_id=entity_id
    )

    entity_attribute_b_changed = VersionedEntity.AttributeChanged(
        name='b',
        value=2,
        originator_version=2,
        originator_id=entity_id
    )

    entity_discarded = VersionedEntity.Discarded(
        originator_version=3,
        originator_id=entity_id
    )


The entity mutator function ``mutate_entity()`` can be used to update the state of an entity from a domain event.

.. code:: python

    from eventsourcing.domain.model.entity import mutate_entity

    entity = mutate_entity(entity, entity_attribute_a_changed)

    assert entity.a == 1


When a versioned entity is updated in this way, the version number is normally incremented.

.. code:: python

    assert entity.version == 2


The method ``_apply()`` can be used to apply an event to the entity.

.. code:: python

    entity._apply(entity_attribute_b_changed)

    assert entity.b == 2
    assert entity.version == 3


The method ``_apply_and_publish()`` can be used to apply and then publish the event to the publish-subscribe mecahnism.

.. code:: python

    entity = VersionedEntity(id=entity_id, version=0)

    assert len(received_events) == 0
    subscribe(handler=receive_event, predicate=is_domain_event)

    # Publish an AttributeChanged event.
    entity.change_attribute(name='full_name', value='Mr Boots')

    assert entity.full_name == 'Mr Boots'

    assert received_events[0].__class__ == VersionedEntity.AttributeChanged
    assert received_events[0].name == 'full_name'
    assert received_events[0].value == 'Mr Boots'

    # Clean up.
    unsubscribe(handler=receive_event, predicate=is_domain_event)
    received_events.clear()


The entity method ``discard()`` can be used to discard the entity, by applying and publishing a ``Discarded``
event, after which the entity is unavailable for further changes.

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


The mutator function will return ``None`` after mutating an entity with a ``Discarded`` event.

.. code:: python

    entity = VersionedEntity(id=entity_id, version=3)

    entity = mutate_entity(entity, entity_discarded)

    assert entity is None


Custom Entities
---------------

The library entity classes can be subclassed and extended by adding attributes and methods.

.. code:: python


    from eventsourcing.domain.model.decorators import attribute


    class User(VersionedEntity):
        def __init__(self, full_name, *args, **kwargs):
            super(User, self).__init__(*args, **kwargs)
            self.full_name = full_name


An entity factory method can construct, apply, and publish the first event of an entity's lifetime. After the event
is published, the new entity will be returned by the factory method.

.. code:: python

    def create_user(full_name):
        created_event = User.Created(full_name=full_name, originator_id='1')
        assert created_event.originator_id
        user_entity = mutate_entity(event=created_event, initial=User)
        publish(created_event)
        return user_entity

    user = create_user(full_name='Mrs Boots')

    assert user.full_name == 'Mrs Boots'


The library's ``@attribute`` decorator provides a property getter and setter, which will apply and publish an
``AttributeChanged`` event when the property is assigned. Simple mutable attributes can be coded simply as an empty
decorated function, such as the ``fullname`` attribute of the ``User`` entity in the code below.

.. code:: python

    from eventsourcing.domain.model.decorators import attribute


    class User(VersionedEntity):

        def __init__(self, full_name, *args, **kwargs):
            super(User, self).__init__(*args, **kwargs)
            self._full_name = full_name

        @attribute
        def full_name(self):
            pass


In the code below, after the entity has been created, assigning to the ``full_name`` attribute causes the entity to be
updated, and an ``AttributeChanged`` event to be published. Both the ``Created`` and ``AttributeChanged`` events are
received by a subscriber.

.. code:: python

    assert len(received_events) == 0
    subscribe(handler=receive_event, predicate=is_domain_event)

    # Publish a Created event.
    user = create_user('Mrs Boots')
    assert user.full_name == 'Mrs Boots'

    # Publish an AttributeChanged event.
    user.full_name = 'Mr Boots'
    assert user.full_name == 'Mr Boots'

    assert len(received_events) == 2
    assert received_events[0].__class__ == VersionedEntity.Created
    assert received_events[0].full_name == 'Mrs Boots'

    assert received_events[1].__class__ == VersionedEntity.AttributeChanged
    assert received_events[1].value == 'Mr Boots'
    assert received_events[1].name == '_full_name'

    # Clean up.
    unsubscribe(handler=receive_event, predicate=is_domain_event)
    received_events.clear()


The entity base classes can also be extended by adding methods that publish events. In general, the arguments of a
method will be used to perform some work. Then, the result of the work will be used to construct a domain event that
represents what happened. And then the domain event will be applied and published. Methods like this normally have no
return value.

.. code:: python

    from eventsourcing.domain.model.decorators import attribute


    class User(VersionedEntity):

        def __init__(self, *args, **kwargs):
            super(User, self).__init__(*args, **kwargs)
            self._password = None

        def set_password(self, raw_password):
            # Do some work using the arguments of a command.
            password = self._encode_password(raw_password)

            # Construct, apply, and publish an event.
            self.change_attribute('_password', password)

        def check_password(self, raw_password):
            password = self._encode_password(raw_password)
            return self._password == password

        def _encode_password(self, password):
            return ''.join(reversed(password))


    user = User(id='1')

    user.set_password('password')
    assert user.check_password('password')


A custom entity can also have custom methods that publish custom events. In the example below, a method
``make_it_so()`` publishes a domain event called ``SomethingHappened``.

To be applied to an entity, custom event classes must be supported by a custom mutator function. In the code below,
the ``mutate_world()`` mutator function extends the library's ``mutate_entity`` function. The ``_mutate()`` function
of ``DomainEntity`` has been overridden so that ``mutate_world()`` will be called when events are applied.

.. code:: python

    from eventsourcing.domain.model.decorators import mutator

    class World(VersionedEntity):

        def __init__(self, *args, **kwargs):
            super(World, self).__init__(*args, **kwargs)
            self.history = []

        class SomethingHappened(VersionedEntity.Event):
            """Published when something happens in the world."""

        def make_it_so(self, something):
            # Do some work using the arguments of a command.
            what_happened = something

            # Construct an event with the results of the work.
            event = World.SomethingHappened(
                what=what_happened,
                originator_id=self.id,
                originator_version=self.version
            )

            # Apply and publish the event.
            self._apply_and_publish(event)

        @classmethod
        def _mutate(cls, initial, event):
            return world_mutator(event=event, initial=initial)


    @mutator
    def world_mutator(initial, event):
        return mutate_entity(initial, event)

    @world_mutator.register(World.SomethingHappened)
    def _(self, event):
        self.history.append(event)
        self._increment_version()
        return self


    world = World(id='1')
    world.make_it_so('dinosaurs')
    world.make_it_so('trucks')
    world.make_it_so('internet')

    assert world.history[0].what == 'dinosaurs'
    assert world.history[1].what == 'trucks'
    assert world.history[2].what == 'internet'


An alternative is to mix in the class ``WithReflexiveMutator`` to your entity class, and define a ``mutator()``
function on the event object itself. A custom base class might help to adopt this style for all events and entities in
your application,

.. code:: python

    from eventsourcing.domain.model.entity import WithReflexiveMutator
    from eventsourcing.domain.model.decorators import mutator


    class Entity(VersionedEntity, WithReflexiveMutator):
        """
        Custom base class for domain entities in this example.
        """

    class World(Entity):
        """
        Example domain entity, coded with mutator functions on the event classes.
        """
        def __init__(self, *args, **kwargs):
            super(World, self).__init__(*args, **kwargs)
            self.history = []

        class SomethingHappened(VersionedEntity.Event):
            def mutate(self, entity):
                entity.history.append(self)
                entity._increment_version()

        def make_it_so(self, something):
            what_happened = something
            event = World.SomethingHappened(
                what=what_happened,
                originator_id=self.id,
                originator_version=self.version
            )
            self._apply_and_publish(event)


    world = World(id='1')
    world.make_it_so('dinosaurs')
    world.make_it_so('trucks')
    world.make_it_so('internet')

    assert world.history[0].what == 'dinosaurs'
    assert world.history[1].what == 'trucks'
    assert world.history[2].what == 'internet'



Aggregate
=========

The library has a domain entity class called ``AggregateRoot``, which postpones the publishing of all events
pending the next call to its ``save()`` method. When the ``save()`` method is called, all such pending events
are published as a single list of events.

Event Player
============

Repository
==========
