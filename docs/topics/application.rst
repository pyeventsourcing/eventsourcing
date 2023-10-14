==================================================
:mod:`~eventsourcing.application` --- Applications
==================================================

This module helps with developing event-sourced applications.

An event-sourced **application** object has command and query
methods used by clients to interact with its domain model.
An application object has an event-sourced **repository** used to obtain already
existing event-sourced aggregates. It also has a **notification log**
that is used to propagate the state of the application as a sequence
of domain event notifications.


Domain-driven design
====================

The book *Domain-Driven Design* describes a "layered architecture" with four layers:
interface, application, domain, and infrastructure. The application layer depends on
the domain and infrastructure layers. The interface layer depends on the application
layer.

Generally speaking, the application layer implements commands which change the
state of the application, and queries which present the state of the application.
The commands and queries ("application services") are called from the interface layer.
By keeping the application and domain logic in the application and domain layers,
different interfaces can be developed for different technologies without duplicating
application and domain logic.

The discussion below continues these ideas, by combining event-sourced aggregates
and persistence objects in an application object that implements "application services"
as object methods.

.. _Application objects:

Application objects
===================

In general, an application combines a stand-alone domain model and infrastructure that
persists the state of that model. In this library, an event-sourced application object
combines an event-sourced domain model with a cohesive mechanism for storing and retrieving
domain events.

The library's :class:`~eventsourcing.application.Application` class brings together objects
from the :doc:`domain </topics/domain>` and :doc:`persistence </topics/persistence>` modules.
It can be used as it is, or subclassed to develop domain-specific event-sourced applications.

The general idea is to name your application object class after the domain supported by its
domain model, or after the "bounded context" supporting a "subdomain" if you are doing DDD.
And then define command and query methods that allow clients to (let's say) create, read,
update and delete your event-sourced domain model aggregates. Domain model aggregates are
discussed in the :doc:`domain module documentation </topics/domain>`. The "ubiquitous language"
of your project should guide the names of the application's command and query methods,
along with those of its :ref:`domain model aggregates <Aggregates>`.

The main features of an application are:

* the :func:`~eventsourcing.application.Application.save` method, used for collecting
  and recording new aggregate events;
* the ``repository`` attribute, with which aggregates are reconstructed;
* the ``notification_log`` attribute, from which the state of the application can be propagated;
* the :func:`~eventsourcing.application.Application.take_snapshot` method;
* the application environment, used to configure an application;
* the command and query methods you define, which implement your "application services".

The :class:`~eventsourcing.application.Application` class defines an object method
:func:`~eventsourcing.application.Application.save` which can be
used to update the recorded state of one or many
:ref:`domain model aggregates <Aggregates>`. The
:func:`~eventsourcing.application.Application.save` method works by using
the aggregate's :func:`~eventsourcing.domain.Aggregate.collect_events` method to collect
pending domain events; the pending domain events are stored by calling the
:func:`~eventsourcing.persistence.EventStore.put` method of application's
:ref:`event store <Store>`.

The :class:`~eventsourcing.application.Application` class defines an
object attribute ``repository`` which holds an :ref:`event-sourced repository <Repository>`.
The repository's :func:`~eventsourcing.application.Repository.get` method can be used by
your application's command and query methods to obtain already existing aggregates.

The :class:`~eventsourcing.application.Application` class defines an
object attribute ``notification_log`` which holds a :ref:`local notification log <Notification log>`.
The notification log can be used to propagate the state of an application as a sequence of
domain event notifications.

The :class:`~eventsourcing.application.Application` class defines an object method
:func:`~eventsourcing.application.Application.take_snapshot` which can
be used for :ref:`snapshotting <Snapshotting>` existing aggregates. Snapshotting
isn't necessary, but can help to reduce the time it takes to access aggregates with
lots of domain events.

The :class:`~eventsourcing.application.Application` class has an ``env`` attribute
which can be redefined on your application classes. Application objects also have
an ``env`` attribute which is determined by a combination of the application class
attribute, the operating system environment, and by an optional constructor argument.

The :class:`~eventsourcing.application.Application` class can be extended with command
and query methods that use :doc:`event-sourced aggregates </topics/domain>`.

.. _Application simple example:

Simple example
==============

In the example below, the ``DogSchool`` application extends the library's
application object base class. The ``Dog`` aggregate is defined and discussed
as the :ref:`simple example <Aggregate simple example>` in the domain module documentation.

..
    #include-when-testing
..
    from dataclasses import dataclass
    from uuid import uuid4

    from eventsourcing.domain import Aggregate, AggregateEvent


    class Dog(Aggregate):
        def __init__(self):
            self.tricks = []

        @classmethod
        def create(cls):
            return cls._create(
                event_class=cls.Created,
                id=uuid4(),
            )

        def add_trick(self, trick):
            self.trigger_event(Dog.TrickAdded, trick=trick)

        class TrickAdded(AggregateEvent):
            trick: str

            def apply(self, dog):
                dog.tricks.append(self.trick)


.. code-block:: python

    from typing import List
    from uuid import UUID

    from eventsourcing.application import Application


    class DogSchool(Application):
        def register_dog(self) -> UUID:
            dog = Dog.create()
            self.save(dog)
            return dog.id

        def add_trick(self, dog_id: UUID, trick: str):
            dog = self.repository.get(dog_id)
            dog.add_trick(trick)
            self.save(dog)

        def get_tricks(self, dog_id: UUID) -> List[str]:
            dog = self.repository.get(dog_id)
            return list(dog.tricks)


The ``register_dog()`` method is defined as a command method that creates and saves a
new ``Dog`` aggregate. It returns a new ``dog_id`` that can be used to identify the
aggregate on subsequence method calls. It saves the new aggregate by calling the base
class :func:`~eventsourcing.application.Application.save` method.

The ``add_trick()`` method is also defined as a command method.
It works by obtaining an existing ``Dog`` aggregate from the repository. Then it calls the
aggregate's command method ``add_trick()``, and then saves the aggregate by calling the
application's :func:`~eventsourcing.application.Application.save` method.

The application's ``get_tricks()`` method is defined as a query method
that presents the current ``tricks`` of an existing ``Dog`` aggregate. It works by
calling the repository :func:`~eventsourcing.application.Repository.get` method to
reconstruct a ``Dog`` aggregate object from previously saved aggregate events, and
then returns the value of its ``tricks`` attribute.

Having define an application object, we can use it. Below, an instance of the
``DogSchool`` application is constructed. A new ``Dog`` aggregate is created
by calling ``register_dog()``. Three items are added to its ``tricks`` by
calling ``add_trick()`` three times. The recorded ``tricks`` of the aggregate
is then obtained by calling ``get_tricks()`` method.

.. code-block:: python

    application = DogSchool()

    dog_id = application.register_dog()

    application.add_trick(dog_id, "roll over")
    application.add_trick(dog_id, "fetch ball")
    application.add_trick(dog_id, "play dead")

    tricks = application.get_tricks(dog_id)
    assert tricks[0] == "roll over"
    assert tricks[1] == "fetch ball"
    assert tricks[2] == "play dead"

In the example above, the application object uses the library's
"plain old Python objects" infrastructure, which keeps stored event
objects in memory. This is the default for all application
objects. To store the domain events in a real database, simply
:ref:`configure persistence<Persistence>` by setting environment
variables for the application.


.. _Repository:

Repository
==========

The application ``repository`` is used to get the already existing aggregates of the
application's domain model. It is an instance of the library's
:class:`~eventsourcing.application.Repository` class.
The repository's :func:`~eventsourcing.application.Repository.get` method is used to
obtain already existing aggregates. It works by calling the
:func:`~eventsourcing.persistence.EventStore.get` method of an
:ref:`event store <Store>` to retrieve already existing
:ref:`domain event objects <Domain events>` for the requested
aggregate, and then using these to reconstruct an aggregate object.


.. code-block:: python

    dog_latest = application.repository.get(dog_id)

    assert len(dog_latest.tricks) == 3
    assert dog_latest.version == 4


The :class:`~eventsourcing.application.Repository` class implements a
:func:`~eventsourcing.application.Repository.__contains__` method, so that
you can use the Python ``in`` keyword to see whether or not an aggregate
exists in the repository.

.. code-block:: python

    assert dog_id in application.repository

    assert uuid4() not in application.repository


The repository :func:`~eventsourcing.application.Repository.get` method accepts
three arguments: ``aggregate_id``, ``version``, and ``projector_func``.
The ``aggregate_id`` argument is required, and should be the ID of an already existing
aggregate. If the aggregate is not found, the exception
:class:`~eventsourcing.application.AggregateNotFound` will be raised.

The ``version`` argument is optional, and represents the required version of the aggregate.
If the requested version is greater than the highest available version of the aggregate, the
highest available version of the aggregate will be returned.

.. code-block:: python

    dog_v1 = application.repository.get(dog_id, version=1)

    assert dog_v1.version == 1
    assert len(dog_v1.tricks) == 0

    dog_v2 = application.repository.get(dog_id, version=2)

    assert dog_v2.version == 2
    assert len(dog_v2.tricks) == 1
    assert dog_v2.tricks[-1] == "roll over"

    dog_v3 = application.repository.get(dog_id, version=3)

    assert dog_v3.version == 3
    assert len(dog_v3.tricks) == 2
    assert dog_v3.tricks[-1] == "fetch ball"

    dog_v4 = application.repository.get(dog_id, version=4)

    assert dog_v4.version == 4
    assert len(dog_v4.tricks) == 3
    assert dog_v4.tricks[-1] == "play dead"

    dog_v5 = application.repository.get(dog_id, version=5)

    assert dog_v5.version == 4  # There is no version 5.
    assert len(dog_v5.tricks) == 3
    assert dog_v5.tricks[-1] == "play dead"

The ``projector_func`` argument is also optional, and can be used to pass in an alternative
"mutator function" that will be used as the "aggregate projector" to reconstruct
the current state of the aggregate from stored snapshots and domain events.
By default, the repository will use the :func:`~eventsourcing.domain.AggregateEvent.mutate`
methods of domain event objects to reconstruct the state of the requested aggregate.

It is possible to enable caching of aggregates in the application repository.
See :ref:`Configuring aggregate caching <Aggregate caching>` for more information.

.. _Notification Log:

Notification log
================

A notification log can be used to propagate the state of an application as a
sequence of domain event notifications. The library's
:class:`~eventsourcing.application.LocalNotificationLog` class presents
the event notifications of an application.
The application object attribute ``notification_log`` is an instance of
:class:`~eventsourcing.application.LocalNotificationLog`.

.. code-block:: python

    from eventsourcing.application import LocalNotificationLog

    assert isinstance(application.notification_log, LocalNotificationLog)


This class implements an abstract base class :class:`~eventsourcing.application.NotificationLog`
which defines method signatures needed by the :class:`~eventsourcing.system.NotificationLogReader`
class, so that a reader can get event notifications from both "local" and "remote" notification
logs. The event notifications themselves are instances of the library's
:class:`~eventsourcing.persistence.Notification` class, which is
defined in the persistence module and discussed in the
:ref:`Notification objects <Notification objects>` section.

The general idea is that, whilst the aggregate events are recorded in a sequence for
the aggregate, all of the aggregate events are also given a "total order" by being
placed in a sequence of event notifications. When recording aggregate events using an
:ref:`application recorder<Recorder>`, event notifications are
automatically and atomically recorded along with the stored events.


Outbox pattern
--------------

The "notification log pattern" is also referred to as the "outbox pattern".
The general idea is to avoid "dual writing" when recording updates to application
state and then messaging those updates to others. The important thing is that either
both the stored events and the notifications are recorded together, or nothing is
recorded. Unless these two things are recorded atomically, in the same database
transaction, it is impossible to exclude the possibility that one will happen but
not the other, potentially causing a permanent and perhaps catastrophic inconsistency
in the state of downstream applications. But it is equally important to avoid
"dual writing" in the consumption of event notifications, which is why "tracking"
records need to be written atomically when recording the result of processing event
notifications. This is a topic we shall return to when discussing the
:doc:`system </topics/system>` module.


Selecting notifications from the log
------------------------------------

The :func:`~eventsourcing.application.LocalNotificationLog.select` method of a
notification log can be used to directly select a sub-sequence of
:ref:`event notification objects <Notification objects>` from a notification log.
In the example below, the first two event notifications are selected from the
notification log of the :class:`~eventsourcing.application.Application` object.

.. code-block:: python

    notifications = application.notification_log.select(start=1, limit=2)


The ``start`` and ``limit`` arguments are used to specify the selection. The
selection will contain no more than the specified ``limit``.

.. code-block:: python

    assert len(notifications) == 2


We can see they are all instances of the :class:`~eventsourcing.persistence.Notification` class.

.. code-block:: python

    from eventsourcing.persistence import Notification

    assert isinstance(notifications[0], Notification)
    assert isinstance(notifications[1], Notification)


Each event notification has an ``id`` that is the unique integer ID of
the event notification. The event notifications are ordered by their IDs,
with later event notifications having higher values than earlier ones.

The selection of event notifications will have notification IDs which are
greater or equal to the given value of ``start``. Please note, by default,
the first recorded event notification will have ID equal to ``1``.

.. code-block:: python

    assert notifications[0].id == 1
    assert notifications[1].id == 2


We can see these notifications represent the facts that a ``Dog`` aggregate was
created, and then two ``TrickAdded`` events occurred ("roll over", "fetch ball").

.. code-block:: python

    notification = notifications[0]
    assert "Dog.Created" in notification.topic
    assert notification.originator_id == dog_id

    notification = notifications[1]
    assert "Dog.TrickAdded" in notification.topic
    assert b"roll over" in notification.state
    assert notification.originator_id == dog_id


We can continue to select event notifications, by using the
last event notification ID to calculate the next ``start`` value.

.. code-block:: python

    notifications = application.notification_log.select(
        start=notifications[-1].id + 1, limit=2
    )

    assert notifications[0].id == 3
    assert notifications[1].id == 4

    notification = notifications[0]
    assert "Dog.TrickAdded" in notification.topic
    assert b"fetch ball" in notification.state

    notification = notifications[1]
    assert "Dog.TrickAdded" in notification.topic
    assert b"play dead" in notification.state


This method is used in a :class:`~eventsourcing.system.NotificationLogReader`
in a :class:`~eventsourcing.system.ProcessApplication` to
pull event notifications from upstream applications in an event-driven system,
using the :func:`~eventsourcing.persistence.ProcessRecorder.max_tracking_id` method
of a :class:`~eventsourcing.persistence.ProcessRecorder` to calculate the
next start value from which to pull unprocessed event notifications.
See the :doc:`system </topics/system>` and :doc:`persistence </topics/persistence>`
module documentation for more information.


Linked list of sections
-----------------------

The notification log also presents linked sections of
:ref:`notification objects <Notification objects>`.
The sections are instances of the library's :class:`~eventsourcing.application.Section` class.

A notification log section is identified by a section ID string that comprises
two integers separated by a comma, for example ``"1,10"``. The first integer
specifies the notification ID of the first event notification included in the
section. The second integer specifies the notification ID of the second event
notification included in the section. Sections are requested from the notification
using the Python square bracket syntax, for example ``application.notification_log["1,10"]``.

The notification log will return a section that has no more than the requested
number of event notifications. Sometimes there will be less event notifications
in the recorded sequence of event notifications than are needed to fill the
section, in which case less than the number of event notifications will be included
in the returned section. On the other hand, there may be gaps in the recorded
sequence of event notifications, in which case the last event notification
included in the section may have a notification ID that is greater than that
which was specified in the requested section ID.

A notification log section has an attribute ``section_id`` that has the section
ID. The section ID value will represent the event notification ID of the first
and the last event notification included in the section. If there are no event
notifications, the section ID will be ``None``.

A notification log section has an attribute ``items`` that has the list of
:ref:`notification objects <Notification objects>` included in the section.

A notification log section has an attribute ``next_id`` that has the section ID
of the next section in the notification log. If the notification log section has
less event notifications that were requested, the ``next_id`` value will be ``None``.

In the example above, there are four domain events in the domain model, and so there
are four notifications in the notification log.

.. code-block:: python

    section = application.notification_log["1,10"]

    assert len(section.items) == 4
    assert section.id == "1,4"
    assert section.next_id is None

    assert isinstance(section.items[0], Notification)
    assert section.items[0].id == 1
    assert section.items[1].id == 2
    assert section.items[2].id == 3
    assert section.items[3].id == 4

    assert section.items[0].originator_id == dog_id
    assert section.items[1].originator_id == dog_id
    assert section.items[2].originator_id == dog_id
    assert section.items[3].originator_id == dog_id

    assert section.items[0].originator_version == 1
    assert section.items[1].originator_version == 2
    assert section.items[2].originator_version == 3
    assert section.items[3].originator_version == 4

    assert "Dog.Created" in section.items[0].topic
    assert "Dog.TrickAdded" in section.items[1].topic
    assert "Dog.TrickAdded" in section.items[2].topic
    assert "Dog.TrickAdded" in section.items[3].topic

    assert b"roll over" in section.items[1].state
    assert b"fetch ball" in section.items[2].state
    assert b"play dead" in section.items[3].state

A domain event can be reconstructed from an event notification by calling the
application's mapper method :func:`~eventsourcing.persistence.Mapper.to_domain_event`.
If the application is configured to encrypt stored events, the event notification
will also be encrypted, but the mapper will decrypt the event notification.

.. code-block:: python

    domain_event = application.mapper.to_domain_event(section.items[0])
    assert isinstance(domain_event, Dog.Created)
    assert domain_event.originator_id == dog_id

    domain_event = application.mapper.to_domain_event(section.items[3])
    assert isinstance(domain_event, Dog.TrickAdded)
    assert domain_event.originator_id == dog_id
    assert domain_event.trick == "play dead"


Registering custom transcodings
===============================

The application serialises and deserialises domain events using a
:ref:`transcoder <Transcoder>` object. By default, the application
will use the library's default JSON transcoder. The library's application
base class registers transcodings for :class:`~uuid.UUID`, :class:`~decimal.Decimal`,
and :class:`~datetime.datetime` objects.

If your domain model uses types of object that are not already supported by
the transcoder, then custom :ref:`transcodings <Transcodings>` for these
objects will need to be implemented and registered with the application's
transcoder.

The application method :func:`~eventsourcing.application.Application.register_transcodings`
can be overridden or extended to register the transcodings required by your application.

For example, to define and register a :class:`~eventsourcing.persistence.Transcoding`
for the Python :class:`~datetime.date` class, define a class such as the
``DateAsISO`` class below, and extend the application
:func:`~eventsourcing.application.Application.register_transcodings`
method by calling the ``super()`` method with the given ``transcoder``
argument, and then the transcoder's :func:`~eventsourcing.persistence.Transcoder.register`
method once for each of your custom transcodings.

.. code-block:: python

    from datetime import date
    from typing import Union

    from eventsourcing.persistence import Transcoder, Transcoding


    class MyApplication(Application):
        def register_transcodings(self, transcoder: Transcoder):
            super().register_transcodings(transcoder)
            transcoder.register(DateAsISO())


    class DateAsISO(Transcoding):
        type = date
        name = "date_iso"

        def encode(self, o: date) -> str:
            return o.isoformat()

        def decode(self, d: Union[str, dict]) -> date:
            assert isinstance(d, str)
            return date.fromisoformat(d)


.. _Saving multiple aggregates:

Saving multiple aggregates
==========================

In some cases, it is necessary to save more than one aggregate in the same atomic
transaction. The persistence modules included in this library all support atomic
recording of aggregate events into more than one aggregate sequence. However, not
all databases can support this, and so this isn't allowed on the library extensions
that adapt these databases.

The example below continues the example from the discussion of
:ref:`namespaced IDs <Namespaced IDs>` in the domain module documentation. The
aggregate classes ``Page`` and ``Index`` are defined in that section.

..
    # include-when-testing
..
    from dataclasses import dataclass
    from uuid import uuid5, NAMESPACE_URL

    from eventsourcing.domain import Aggregate, AggregateEvent, AggregateCreated


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

        class Created(AggregateCreated):
            name: str
            body: str

        def update_name(self, name: str):
            self.trigger_event(self.NameUpdated, name=name)

        class NameUpdated(AggregateEvent):
            name: str

            def apply(self, page: "Page"):
                page.name = self.name


    class Index(Aggregate):
        def __init__(self, ref):
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

        class Created(AggregateCreated):
            ref: UUID

        def update_ref(self, ref):
            self.trigger_event(self.RefUpdated, ref=ref)

        class RefUpdated(AggregateEvent):
            ref: UUID

            def apply(self, index: "Index"):
                index.ref = self.ref


We can define a simple wiki application, which creates named
pages. Pages can be retrieved by name. Names can be changed
and the pages can be retrieved by the new name.

.. code-block:: python

    class Wiki(Application):
        def create_page(self, name: str, body: str) -> None:
            page = Page.create(name, body)
            index = Index.create(page)
            self.save(page, index)

        def rename_page(self, name: str, new_name: str) -> None:
            page = self.get_page(name)
            page.update_name(new_name)
            index = Index.create(page)
            self.save(page, index)
            return page.body

        def get_page(self, name: str) -> Page:
            index_id = Index.create_id(name)
            index = self.repository.get(index_id)
            page_id = index.ref
            return self.repository.get(page_id)


Now let's construct the application object and create a new page (with a deliberate spelling mistake).

.. code-block:: python


    wiki = Wiki()

    wiki.create_page(name="Erth", body="Lorem ipsum...")


We can use the page name to retrieve the body of the page.

.. code-block:: python

    assert wiki.get_page(name="Erth").body == "Lorem ipsum..."


We can also update the name of the page, and then retrieve the page using the new name.

.. code-block:: python

    wiki.rename_page(name="Erth", new_name="Earth")

    assert wiki.get_page(name="Earth").body == "Lorem ipsum..."


The uniqueness constraint on the recording of stored domain event objects combined
with the atomicity of recording domain events means that name collisions in the
index will result in the wiki not being updated.

.. code-block:: python

    from eventsourcing.persistence import RecordConflictError

    # Can't create another page using an existing name.
    try:
        wiki.create_page(name="Earth", body="Neque porro quisquam...")
    except RecordConflictError:
        pass
    else:
        raise AssertionError("RecordConflictError not raised")

    assert wiki.get_page(name="Earth").body == "Lorem ipsum..."

    # Can't rename another page to an existing name.
    wiki.create_page(name="Mars", body="Neque porro quisquam...")
    try:
        wiki.rename_page(name="Mars", new_name="Earth")
    except RecordConflictError:
        pass
    else:
        raise AssertionError("RecordConflictError not raised")

    assert wiki.get_page(name="Earth").body == "Lorem ipsum..."
    assert wiki.get_page(name="Mars").body == "Neque porro quisquam..."


A :doc:`more refined implementation </topics/examples/content-management>` might release
old index objects when page names are changed so that they can be reused by other pages,
or update the old index to point to the new index, so that redirects can be implemented.
See the :doc:`Wiki application example </topics/examples/content-management>` to see how
this can be done.

Using index aggregates, or aggregates with version-5 UUIDs is one way to
discover version-4 aggregate IDs. By knowing the name, the IDs can be
retrieved. A more powerful alternative is to implement a custom table
of current values that can be used to index a collection of aggregates,
but this requires a little bit more work. Another alternative is to
have an aggregate that is a collection of many version-4 aggregate IDs,
or even other attribute values, that can be used to the same effect.
But this approach has limits because there may be too many aggregate IDs
to contain in a single collection aggregate without suffering from performance
issues. Another way that avoids the limits of collecting version-4 aggregate IDs
in an event-sourced aggregate identified with a version-5 UUID is to use an
event-sourced log.

..
    #Todo: Show how to use ORM objects for read model.

.. _event-sourced-log:

Event-sourced log
=================

As we have seen, event-sourced aggregates generate a sequence of events. The
stored sequence of events can be retrieved and projected to reconstruct the
current state of the aggregate. However, the mechanism for storing and retrieving
events in a sequence is useful in itself. We can usefully log a sequence of events,
and use this sequence without projecting the entire sequence into the current state
of an aggregate. The term 'event-sourced log' refers to using the persistence mechanism
for event sourcing without aggregate projections for the purpose of logging information
that is useful in an application.

An event-sourced log object can be constructed as a part of an application. The library
class :class:`~eventsourcing.application.EventSourcedLog` can be used as an event-sourced
log. An event-sourced log object is typically constructed with a version-5 UUID that
identifies the sequence of logged events, and a subclass of :class:`~eventsourcing.domainmodel.DomainEvent`
defined with attributes for the information to be logged.  A "trigger" method can be defined
that expects to be given the kind of information to be logged. The "trigger" method constructs
and returns a new event object of the given type with the given information. The event can
then be saved atomically with other things, by passing it to the application's
:func:`~eventsourcing.application.Application.save` method. A subsequence of logged
events, of a given size and from a given position, can be selected from log. The logged
information can be used directly.

This technique can be used, for example, to record and later discover the version-4
UUIDs of a particular type of aggregate. In the example below, aggregate IDs of newly
created aggregates are logged, so that the aggregate IDs of stored aggregates can be
discovered. The aggregate IDs are then accessed in pages of a fixed size.

.. code-block:: python

    from eventsourcing.application import EventSourcedLog
    from eventsourcing.domain import DomainEvent


    class LoggedID(DomainEvent):
        aggregate_id: UUID


    class MyApplication(Application):
        def __init__(self, env=None) -> None:
            super().__init__(env=env)
            self.aggregate_log = EventSourcedLog(
                events=self.events,
                originator_id=uuid5(NAMESPACE_URL, "/aggregates"),
                logged_cls=LoggedID,
            )

        def create_aggregate(self):
            aggregate = Aggregate()
            log_event = self.aggregate_log.trigger_event(
                aggregate_id=aggregate.id
            )
            self.save(aggregate, log_event)
            return aggregate.id


    app = MyApplication()

    # Get last created aggregate ID.
    assert app.aggregate_log.get_last() == None

    aggregate1_id = app.create_aggregate()
    last = app.aggregate_log.get_last()
    assert last.aggregate_id == aggregate1_id

    aggregate2_id = app.create_aggregate()
    last = app.aggregate_log.get_last()
    assert last.aggregate_id == aggregate2_id

    # Get all created aggregate ID.
    aggregate_ids = [i.aggregate_id for i in app.aggregate_log.get()]
    assert aggregate_ids == [aggregate1_id, aggregate2_id]

    aggregate_ids = [i.aggregate_id for i in app.aggregate_log.get(desc=True)]
    assert aggregate_ids == [aggregate2_id, aggregate1_id]

    # Get ascending pages of aggregate IDs.
    log_events = list(app.aggregate_log.get(limit=1))
    aggregate_ids = [i.aggregate_id for i in log_events]
    assert aggregate_ids == [aggregate1_id]

    next = log_events[-1].originator_version
    log_events = app.aggregate_log.get(limit=1, gt=next)
    aggregate_ids = [i.aggregate_id for i in log_events]
    assert aggregate_ids == [aggregate2_id]

    # Get descending pages of aggregate IDs.
    log_events = list(app.aggregate_log.get(desc=True, limit=1))
    aggregate_ids = [i.aggregate_id for i in log_events]
    assert aggregate_ids == [aggregate2_id]

    next = log_events[-1].originator_version - 1
    log_events = app.aggregate_log.get(desc=True, limit=1, lte=next)
    aggregate_ids = [i.aggregate_id for i in log_events]
    assert aggregate_ids == [aggregate1_id]


This technique can be used to implement "list-detail" views common in
non-event-sourced CRUD or ORM-based domain models in which the list is
ordered by the aggregates' :py:obj:`~eventsourcing.domain.Aggregate.created_on`
attribute (ascending or descending).

To order aggregates by another attribute, such as their
:py:obj:`~eventsourcing.domain.Aggregate.modified_on` value,
or a custom attribute, it will be necessary somehow to define
and maintain a custom index of the current values. Similarly, a
custom index will need to be maintained if aggregates are to be
discarded, since it isn't possible to delete events from the log.


.. _Application configuration:

Application configuration
=========================

An application can be configured using environment variables. You
can set the application's environment either on the ``env``
attribute of the application class, in the
`operating system environment <https://docs.python.org/3/library/os.html#os.environ>`_,
or by passing them into the application using the constructor argument ``env``. You
can use all three ways for configuring an application in combination.

.. code-block:: python

    import os

    # Configure by setting class attribute.
    class MyApplication(Application):
        env = {"SETTING_A": "1", "SETTING_B": "1", "SETTING_C": "1"}

    # Configure by setting operating system environment.
    os.environ["SETTING_B"] = "2"
    os.environ["SETTING_C"] = "2"

    # Configure by setting constructor argument.
    app = MyApplication(env={"SETTING_C": "3"})

The order of precedence
is: constructor argument, operating system, class attribute. This means a constructor
argument setting will override both an operating system and a class attribute setting. And
an operating system setting will override a class attribute setting.

.. code-block:: python

    assert app.env["SETTING_A"] == "1"
    assert app.env["SETTING_B"] == "2"
    assert app.env["SETTING_C"] == "3"

The resulting settings can be seen on the ``env`` attribute of the application object.
In the example above, we can see that the settings from the construct argument have
overridden the settings from the operating system environment, and the settings from
the operating system environment have overridden the settings from the class attribute.

Please note, all values are expected to be strings, as would be the case if the values
are set in the actual operating system process environment.

.. _Aggregate caching:

Configuring aggregate caching
=============================

To enable caching of aggregates in an :ref:`application repository <Repository>`,
set ``AGGREGATE_CACHE_MAXSIZE`` in the application
environment to a string representing an integer value. A positive integer value
such as ``'1000'`` will enable a "least recently used" cache, in which the least
recently used aggregate will be evicted from the cache when it is full.
A value of ``'0'`` will enable an unlimited cache. The default is for
aggregate caching not to be enabled.

When getting an aggregate that is not found in the cache, the aggregate
will be reconstructed from stored events, and then placed in the cache.
When getting an aggregate that is found in the cache, it will be "deep copied"
to prevent the cache being corrupted with partial or aborted changes made
by an application command method. After a mutated aggregate is successfully
saved, the cache is updated by replacing the old state of the aggregate with
the new.

To avoid an application getting stale aggregates from a repository when
aggregate caching is enabled (that is, aggregates for which subsequent events
have been stored outside of the application instance) cached aggregates are
"fast-forwarded" with any subsequent events. This involves querying for subsequent
events, and updating the state of the aggregate.

To disable fast-forwarding of cached aggregates, set ``AGGREGATE_CACHE_FASTFORWARD`` in
the application environment to a false value as interpreted by :func:`~eventsourcing.utils.strtobool`,
that is one of ``'n'``, ``'no'``, ``'f'``, ``'false'``, ``'off'``, or ``'0'``. Only do
this when only one instance of the application is being used to evolve the state of the
aggregates, because integrity errors will certainly occur when attempting to evolve the
state of stale aggregates. The default is for fast-forwarding to be enabled when aggregate
caching is enabled. But in cases where there is only one application instance,
querying for new events is unnecessary, and a greater performance improvement
will be obtained by disabling fast-forwarding because querying for new events
will be avoided.

.. _Persistence:

Configuring persistence
=======================

By default, application objects will be configured to use the library's
"plain old Python objects" persistence module, and will store events in memory.
The example above uses the application's default persistence module.
This is good for development, because it is the fastest option. But the
state of the application will be lost when the application object is
deleted. So it is not very good for production.

If you want the state of the application object to endure, you will need to
use an alternative persistence module. To use alternative persistence
infrastructure, set the variable ``PERSISTENCE_MODULE`` in the application
environment. Using an alternative persistence module may involve setting
further environment variables, perhaps to configure access to a real database,
such as a database name, a user name, and a password.

For example, to use the library's :ref:`SQLite persistence module <sqlite-module>`,
set ``PERSISTENCE_MODULE`` to the value ``"eventsourcing.sqlite"``.
The environment variable ``SQLITE_DBNAME`` must also be set. This value
will be passed to Python's :func:`sqlite3.connect` function.

.. code-block:: python

    from tempfile import NamedTemporaryFile

    tmpfile = NamedTemporaryFile(suffix="_eventsourcing_test.db")

    os.environ["PERSISTENCE_MODULE"] = "eventsourcing.sqlite"
    os.environ["SQLITE_DBNAME"] = tmpfile.name
    application = DogSchool()

    dog_id = application.register_dog()

    application.add_trick(dog_id, "roll over")
    application.add_trick(dog_id, "fetch ball")
    application.add_trick(dog_id, "play dead")


By using a file on disk, as we did in the example above, the state of
the application will endure after the application object has been deleted
and reconstructed.

.. code-block:: python

    del application

    application = DogSchool()

    tricks = application.get_tricks(dog_id)
    assert tricks[0] == "roll over"
    assert tricks[1] == "fetch ball"
    assert tricks[2] == "play dead"

See :ref:`SQLite module <sqlite-module>` documentation for more information
about using SQLite.

To use the library's PostgreSQL persistence module,
set ``PERSISTENCE_MODULE`` to the value ``"eventsourcing.postgres"``.
See :ref:`PostgreSQL module <postgres-module>` documentation
for more information about using PostgreSQL.


Configuring compression
=======================

Compression is useful for reducing the total size of recorded
application state, and for reducing transport time of domain
events and domain event notifications across a network.

To enable compression, set the environment variable ``COMPRESSOR_TOPIC``
as the :ref:`topic <Topics>` of a compressor class or module.
The  library's :class:`~eventsourcing.compressor.ZlibCompressor`
can be used to compress stored domain events.

.. code-block:: python

    # Configure compressor topic.
    os.environ["COMPRESSOR_TOPIC"] = "eventsourcing.compressor:ZlibCompressor"


Configuring encryption
======================

Application-level encryption is useful for encrypting the state
of the application "on the wire" and "at rest".

To enable application-level encryption, set the environment variable
``CIPHER_TOPIC`` to be the :ref:`topic <Topics>` of a cipher class.

The library's :class:`~eventsourcing.cipher.AESCipher` class can
be used to encrypt stored domain events.
When using the library's :class:`~eventsourcing.cipher.AESCipher`
class, set environment variable ``CIPHER_KEY`` to be a valid encryption
key. You can use the static method :func:`~eventsourcing.cipher.AESCipher.create_key`
on the :class:`~eventsourcing.cipher.AESCipher` class to generate a valid encryption key.

.. code-block:: python

    from eventsourcing.cipher import AESCipher

    # Generate a cipher key (keep this safe).
    cipher_key = AESCipher.create_key(num_bytes=32)

    # Configure cipher topic.
    os.environ["CIPHER_TOPIC"] = "eventsourcing.cipher:AESCipher"

    # Configure cipher key.
    os.environ["CIPHER_KEY"] = cipher_key


.. _Snapshotting:

Snapshotting
============

If the reconstruction of an aggregate depends on obtaining and replaying
a relatively large number of domain event objects, it can take a relatively
long time to reconstruct the aggregate. Snapshotting aggregates can help to
reduce the time it takes to reconstruct aggregates, and hence reduce the access
time of aggregates with lots of domain events.

Snapshots are stored separately from the aggregate events. When snapshotting
is enabled, the application object will have a snapshot store assigned to the
attribute ``snapshots``. By default, snapshotting is not enabled, and the application
object's ``snapshots`` attribute will have the value ``None``.

.. code-block:: python

    assert application.snapshots is None

Enabling snapshotting
---------------------

To enable snapshotting in application objects, the environment variable
``IS_SNAPSHOTTING_ENABLED`` may be set to a valid "true"  value. The
function :func:`~eventsourcing.utils.strtobool` is used to interpret
the value of this environment variable, so that strings
``"y"``, ``"yes"``, ``"t"``, ``"true"``, ``"on"`` and ``"1"`` are considered to
be "true" values, and ``"n"``, ``"no"``, ``"f"``, ``"false"``, ``"off"`` and ``"0"``
are considered to be "false" values, and other values are considered to be invalid.
The default is for an application's snapshotting functionality not to be enabled.

.. code-block:: python

    application = DogSchool(env={"IS_SNAPSHOTTING_ENABLED": "y"})

    assert application.snapshots is not None


Snapshotting can also be enabled for all instances of an application class by
setting the boolean attribute 'is_snapshotting_enabled' on the application class.

.. code-block:: python

    class SnapshottingApplication(Application):
        is_snapshotting_enabled = True

    application = SnapshottingApplication()
    assert application.snapshots is not None


Taking snapshots
----------------

The application method :func:`~eventsourcing.application.Application.take_snapshot`
can be used to create a snapshot of the state of an aggregate. The ID of an aggregate
to be snapshotted must be passed when calling this method. By passing in the ID
(and optional version number), rather than an actual aggregate object, the risk of
snapshotting a somehow "corrupted" aggregate object that does not represent the
actually recorded state of the aggregate is avoided.

.. code-block:: python

    application = DogSchool(env={"IS_SNAPSHOTTING_ENABLED": "y"})
    dog_id = application.register_dog()

    application.add_trick(dog_id, "roll over")
    application.add_trick(dog_id, "fetch ball")
    application.add_trick(dog_id, "play dead")

    application.take_snapshot(dog_id)


Snapshots are stored separately from the aggregate events, but snapshot objects are
implemented as a kind of domain event, and snapshotting uses the same mechanism
for storing snapshots as for storing aggregate events. When snapshotting is enabled,
the application object attribute ``snapshots`` is an event store dedicated to storing
snapshots. The snapshots can be retrieved from the snapshot store using the
:func:`~eventsourcing.persistence.EventStore.get` method. We can get the latest snapshot
by selecting in descending order with a limit of 1.

.. code-block:: python

    snapshots = application.snapshots.get(dog_id, desc=True, limit=1)

    snapshots = list(snapshots)
    assert len(snapshots) == 1, len(snapshots)
    snapshot = snapshots[0]

    assert snapshot.originator_id == dog_id
    assert snapshot.originator_version == 4

When snapshotting is enabled, the application repository looks for snapshots in this way.
If a snapshot is found by the aggregate repository when retrieving an aggregate,
then only the snapshot and subsequent aggregate events will be retrieved and used
to reconstruct the state of the aggregate.


.. _automatic-snapshotting:

Automatic snapshotting
----------------------

Automatic snapshotting of aggregates at regular intervals can be enabled
for an application class be setting the class attribute 'snapshotting_intervals'.
The 'snapshotting_intervals' should be a mapping of aggregate classes to integers
which represent the snapshotting interval. Setting this attribute implicitly
enables snapshotting as described above. When aggregates are saved, snapshots
will be taken if the version of aggregate coincides with the specified interval.

The example extends the ``DogSchool`` application class and specifies
that ``Dog`` aggregates are to be automatically snapshotted every
2 events. In practice, a suitable interval would most likely be larger
than 2, perhaps more like 100.

.. code-block:: python

    class DogSchoolWithAutomaticSnapshotting(DogSchool):
        snapshotting_intervals = {Dog: 2}


    application = DogSchoolWithAutomaticSnapshotting()

    dog_id = application.register_dog()

    application.add_trick(dog_id, "roll over")
    application.add_trick(dog_id, "fetch ball")
    application.add_trick(dog_id, "play dead")

    snapshots = application.snapshots.get(dog_id)
    snapshots = list(snapshots)

    assert len(snapshots) == 2

    assert snapshots[0].originator_id == dog_id
    assert snapshots[0].originator_version == 2

    assert snapshots[1].originator_id == dog_id
    assert snapshots[1].originator_version == 4


Classes
=======

.. automodule:: eventsourcing.application
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__

.. automodule:: eventsourcing.cipher
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__

.. automodule:: eventsourcing.compressor
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__
