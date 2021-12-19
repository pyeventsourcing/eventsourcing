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

* the command and query methods you define, which implement your "application services";
* the :func:`~eventsourcing.application.Application.save` method, used for collecting
  and recording new aggregate events;
* the ``repository`` object, with which aggregates are reconstructed;
* the notification ``log`` object, from which the state of the application can be propagated;
* the :func:`~eventsourcing.application.Application.take_snapshot` method;
* the application's ``env``, through which the application can be configured.

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
object attribute ``log`` which holds a :ref:`local notification log <Notification log>`.
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


Basic example
=============

In the example below, the ``Worlds`` application extends the library's
application object base class. The ``World`` aggregate is defined and discussed
as the :ref:`Simple example <Aggregate simple example>` in the domain module documentation.

..
    #include-when-testing
..
    from dataclasses import dataclass
    from uuid import uuid4

    from eventsourcing.domain import Aggregate, AggregateEvent


    class World(Aggregate):
        def __init__(self):
            self.history = []

        @classmethod
        def create(cls):
            return cls._create(
                event_class=cls.Created,
                id=uuid4(),
            )

        def make_it_so(self, what):
            self.trigger_event(World.SomethingHappened, what=what)

        class SomethingHappened(AggregateEvent):
            what: str

            def apply(self, world):
                world.history.append(self.what)


.. code-block:: python

    from typing import List
    from uuid import UUID

    from eventsourcing.application import Application


    class Worlds(Application):
        def create_world(self) -> UUID:
            world = World.create()
            self.save(world)
            return world.id

        def make_it_so(self, world_id: UUID, what: str):
            world = self.repository.get(world_id)
            world.make_it_so(what)
            self.save(world)

        def get_world_history(self, world_id: UUID) -> List[str]:
            world = self.repository.get(world_id)
            return list(world.history)


The ``create_world()`` method is defined as a command method
that creates and saves new ``World`` aggregates, returning a new ``world_id`` that can be
used to identify the aggregate on subsequence method calls. It saves the new
aggregate by calling the base class :func:`~eventsourcing.application.Application.save` method.

The ``make_it_so()`` method is also defined as a command method.
It works by obtaining an existing ``World`` aggregate from the repository. Then it calls the
aggregate's command method ``make_it_so()``, and then saves the aggregate by calling the
application's :func:`~eventsourcing.application.Application.save` method.

The application's ``get_world_history()`` method is defined as a query method
that presents the current ``history`` of an existing ``World`` aggregate. It works by
calling the repository :func:`~eventsourcing.application.Repository.get` method to
reconstruct a ``World`` aggregate object from previously saved aggregate events, and
then returns the value of its ``history`` attribute.

Having define an application object, we can use it. Below, an instance of the
``Worlds`` application is constructed. A new ``World`` aggregate is created
by calling ``create_world()``. Three items are added to its ``history`` by
calling ``make_it_so()`` three times. The recorded ``history`` of the aggregate
is then obtained by calling ``get_world_history()`` method.

.. code-block:: python

    application = Worlds()

    world_id = application.create_world()

    application.make_it_so(world_id, "dinosaurs")
    application.make_it_so(world_id, "trucks")
    application.make_it_so(world_id, "internet")

    history = application.get_world_history(world_id)
    assert history[0] == "dinosaurs"
    assert history[1] == "trucks"
    assert history[2] == "internet"

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

    world_latest = application.repository.get(world_id)

    assert len(world_latest.history) == 3
    assert world_latest.version == 4

The repository :func:`~eventsourcing.application.Repository.get` method accepts
three arguments: ``aggregate_id``, ``version``, and ``projector_func``.
The ``aggregate_id`` argument is required, and should be the ID of an already existing
aggregate. If the aggregate is not found, the exception
:class:`~eventsourcing.application.AggregateNotFound` will be raised.

The ``version`` argument is optional, and represents the required version of the aggregate.
If the requested version is greater than the highest available version of the aggregate, the
highest available version of the aggregate will be returned.

.. code-block:: python

    world_v1 = application.repository.get(world_id, version=1)

    assert world_v1.version == 1
    assert len(world_v1.history) == 0

    world_v2 = application.repository.get(world_id, version=2)

    assert world_v2.version == 2
    assert len(world_v2.history) == 1
    assert world_v2.history[-1] == "dinosaurs"

    world_v3 = application.repository.get(world_id, version=3)

    assert world_v3.version == 3
    assert len(world_v3.history) == 2
    assert world_v3.history[-1] == "trucks"

    world_v4 = application.repository.get(world_id, version=4)

    assert world_v4.version == 4
    assert len(world_v4.history) == 3
    assert world_v4.history[-1] == "internet"

    world_v5 = application.repository.get(world_id, version=5)

    assert world_v5.version == 4  # There is no version 5.
    assert len(world_v5.history) == 3
    assert world_v5.history[-1] == "internet"

The ``projector_func`` argument is also optional, and can be used to pass in an alternative
"mutator function" that will be used as the "aggregate projector" to reconstruct
the current state of the aggregate from stored snapshots and domain events.
By default, the repository will use the :func:`~eventsourcing.domain.AggregateEvent.mutate`
methods of domain event objects to reconstruct the state of the requested aggregate.


.. _Notification Log:

Notification log
================

A notification log can be used to propagate the state of an application as a
sequence of domain event notifications. The library's
:class:`~eventsourcing.application.LocalNotificationLog` class presents
the event notifications of an application.
The application object attribute ``log`` is an instance of
:class:`~eventsourcing.application.LocalNotificationLog`.

.. code-block:: python

    from eventsourcing.application import LocalNotificationLog

    assert isinstance(application.log, LocalNotificationLog)


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
In the example below, the first three event notifications are selected from the
notification log of the ``application`` object.

.. code-block:: python

    notifications = application.log.select(start=1, limit=3)


The ``start`` and ``limit`` arguments are used to specify the selection. The
selection will contain no more than the specified ``limit``.

.. code-block:: python

    assert len(notifications) == 3


We can see they are all instances of the :class:`~eventsourcing.persistence.Notification` class.

.. code-block:: python

    from eventsourcing.persistence import Notification

    assert isinstance(notifications[0], Notification)
    assert isinstance(notifications[1], Notification)
    assert isinstance(notifications[2], Notification)


Each event notification has an ``id`` that is the unique integer ID of
the event notification. The event notifications are ordered by their IDs,
with later event notifications having higher values than earlier ones.

The selection of event notifications will have notification IDs which are
greater or equal to the given value of ``start``. Please note, by default,
the first recorded event notification will have ID equal to ``1``.

.. code-block:: python

    assert notifications[0].id == 1
    assert notifications[1].id == 2
    assert notifications[2].id == 3


We can see these notifications represent the facts that a ``World`` aggregate was
created, and then two ``SomethingHappened`` events occurred ("dinosaurs", "trucks").

.. code-block:: python

    notification = notifications[0]
    assert "World.Created" in notification.topic
    assert notification.originator_id == world_id

    notification = notifications[1]
    assert "World.SomethingHappened" in notification.topic
    assert b"dinosaurs" in notification.state
    assert notification.originator_id == world_id

    notification = notifications[2]
    assert "World.SomethingHappened" in notification.topic
    assert b"trucks" in notification.state
    assert notification.originator_id == world_id


We can continue to select event notifications, by using the
last event notification ID to calculate the next ``start`` value.

.. code-block:: python

    notifications = application.log.select(
        start=notification.id + 1, limit=3
    )

    notification = notifications[0]
    assert "World.SomethingHappened" in notification.topic
    assert b"internet" in notification.state


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
using the Python square bracket syntax, for example ``application.log["1,10"]``.

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

    section = application.log["1,10"]

    assert len(section.items) == 4
    assert section.id == "1,4"
    assert section.next_id is None

    assert isinstance(section.items[0], Notification)
    assert section.items[0].id == 1
    assert section.items[1].id == 2
    assert section.items[2].id == 3
    assert section.items[3].id == 4

    assert section.items[0].originator_id == world_id
    assert section.items[1].originator_id == world_id
    assert section.items[2].originator_id == world_id
    assert section.items[3].originator_id == world_id

    assert section.items[0].originator_version == 1
    assert section.items[1].originator_version == 2
    assert section.items[2].originator_version == 3
    assert section.items[3].originator_version == 4

    assert "World.Created" in section.items[0].topic
    assert "World.SomethingHappened" in section.items[1].topic
    assert "World.SomethingHappened" in section.items[2].topic
    assert "World.SomethingHappened" in section.items[3].topic

    assert b"dinosaurs" in section.items[1].state
    assert b"trucks" in section.items[2].state
    assert b"internet" in section.items[3].state

A domain event can be reconstructed from an event notification by calling the
application's mapper method :func:`~eventsourcing.persistence.Mapper.to_domain_event`.
If the application is configured to encrypt stored events, the event notification
will also be encrypted, but the mapper will decrypt the event notification.

.. code-block:: python

    domain_event = application.mapper.to_domain_event(section.items[0])
    assert isinstance(domain_event, World.Created)
    assert domain_event.originator_id == world_id

    domain_event = application.mapper.to_domain_event(section.items[3])
    assert isinstance(domain_event, World.SomethingHappened)
    assert domain_event.originator_id == world_id
    assert domain_event.what == "internet"


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


.. _Application environment:

Application environment
=======================

An application can be configured using environment variables. You
can set the application's environment either on the ``env``
attribute of the application class, in the
`operating system environment <https://docs.python.org/3/library/os.html#os.environ>`__,
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

For example, to use the library's SQLite persistence module,
set ``PERSISTENCE_MODULE`` to the value ``"eventsourcing.sqlite"``.
The environment variable ``SQLITE_DBNAME`` must also be set. This value
will be passed to Python's :func:`sqlite3.connect` function.

.. code-block:: python

    from tempfile import NamedTemporaryFile

    tmpfile = NamedTemporaryFile(suffix="_eventsourcing_test.db")

    os.environ["PERSISTENCE_MODULE"] = "eventsourcing.sqlite"
    os.environ["SQLITE_DBNAME"] = tmpfile.name
    application = Worlds()

    world_id = application.create_world()

    application.make_it_so(world_id, "dinosaurs")
    application.make_it_so(world_id, "trucks")
    application.make_it_so(world_id, "internet")


By using a file on disk, as we did in the example above, the state of
the application will endure after the application object has been deleted
and reconstructed.

.. code-block:: python

    del(application)

    application = Worlds()

    history = application.get_world_history(world_id)
    assert history[0] == "dinosaurs"
    assert history[1] == "trucks"
    assert history[2] == "internet"

See :ref:`SQLite infrastructure <SQLite>` for more information
about using SQLite.

To use the library's PostgreSQL persistence module,
set ``PERSISTENCE_MODULE`` to the value ``"eventsourcing.postgres"``.
See :ref:`PostgreSQL infrastructure <PostgreSQL>` documentation
for more information about using PostgreSQL.


Encryption and compression
==========================

Application-level encryption is useful for encrypting the state
of the application "on the wire" and "at rest". Compression is
useful for reducing transport time of domain events and domain
event notifications across a network and for reducing the total
size of recorded application state.

To enable encryption, set the environment variable ``CIPHER_TOPIC``
to be the :ref:`topic <Topics>` of a cipher class, and ``CIPHER_KEY``
to be a valid encryption key. To enable compression, set the environment
variable ``COMPRESSOR_TOPIC`` to be the :ref:`topic <Topics>` of a
compressor class or module.

The library's :class:`~eventsourcing.cipher.AESCipher` class can
be used to encrypt stored domain events. The Python :mod:`zlib` module
can be used to compress stored domain events.
When using the library's :class:`~eventsourcing.cipher.AESCipher` class,
you can use its static method :func:`~eventsourcing.cipher.AESCipher.create_key`
to generate a valid encryption key.


.. code-block:: python

    from eventsourcing.cipher import AESCipher

    # Generate a cipher key (keep this safe).
    cipher_key = AESCipher.create_key(num_bytes=32)

    # Configure cipher key.
    os.environ["CIPHER_KEY"] = cipher_key

    # Configure cipher topic.
    os.environ["CIPHER_TOPIC"] = "eventsourcing.cipher:AESCipher"

    # Configure compressor topic.
    os.environ["COMPRESSOR_TOPIC"] = "zlib"


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


A :doc:`more refined implementation </topics/examples/wiki>` might release old index objects
when page names are changed so that they can be reused by other
pages, or update the old index to point to the new index, so that
redirects can be implemented. See the :doc:`Wiki application example </topics/examples/wiki>`
to see how this can be done.


..
    #Todo: Register custom transcodings on transcoder.
    #Todo: Show how to use UUID5.
    #Todo: Show how to use ORM objects for read model.

.. _Snapshotting:

Snapshotting
============

If the reconstruction of an aggregate depends on obtaining and replaying
a relatively large number of domain event objects, it can take a relatively
long time to reconstruct the aggregate. Snapshotting aggregates can help to
reduce access time of aggregates with lots of domain events.

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
The default is for an application's snapshotting functionality to be not enabled.

Application environment variables can be passed into the application using the
``env`` argument when constructing an application object. Snapshotting can be
enabled (or disabled) for an individual application object in this way.

.. code-block:: python

    application = Worlds(env={"IS_SNAPSHOTTING_ENABLED": "y"})

    assert application.snapshots is not None


Application environment variables can be also be set in the operating system environment.
Setting operating system environment variables will affect all applications created in
that environment.

.. code-block:: python

    os.environ["IS_SNAPSHOTTING_ENABLED"] = "y"

    application = Worlds()

    assert application.snapshots is not None

    del os.environ["IS_SNAPSHOTTING_ENABLED"]


Values passed into the application object will override operating system environment variables.

.. code-block:: python

    os.environ["IS_SNAPSHOTTING_ENABLED"] = "y"
    application = Worlds(env={"IS_SNAPSHOTTING_ENABLED": "n"})

    assert application.snapshots is None

    del os.environ["IS_SNAPSHOTTING_ENABLED"]

Snapshotting can also be enabled for all instances of an application class by
setting the boolean attribute 'is_snapshotting_enabled' on the application class.

.. code-block:: python

    class WorldsWithSnapshottingEnabled(Worlds):
        is_snapshotting_enabled = True


    application = WorldsWithSnapshottingEnabled()
    assert application.snapshots is not None

However, this setting will also be overridden by both the construct arg ``env``
and by the operating system environment. The example below demonstrates this
by extending the ``Worlds`` application class defined above.

.. code-block:: python

    application = WorldsWithSnapshottingEnabled(env={"IS_SNAPSHOTTING_ENABLED": "n"})

    assert application.snapshots is None

    os.environ["IS_SNAPSHOTTING_ENABLED"] = "n"
    application = WorldsWithSnapshottingEnabled()

    assert application.snapshots is None

    del os.environ["IS_SNAPSHOTTING_ENABLED"]


Taking snapshots
----------------

The application method :func:`~eventsourcing.application.Application.take_snapshot`
can be used to create a snapshot of the state of an aggregate. The ID of an aggregate
to be snapshotted must be passed when calling this method. By passing in the ID
(and optional version number), rather than an actual aggregate object, the risk of
snapshotting a somehow "corrupted" aggregate object that does not represent the
actually recorded state of the aggregate is avoided.

.. code-block:: python

    application = Worlds(env={"IS_SNAPSHOTTING_ENABLED": "y"})
    world_id = application.create_world()

    application.make_it_so(world_id, "dinosaurs")
    application.make_it_so(world_id, "trucks")
    application.make_it_so(world_id, "internet")

    application.take_snapshot(world_id)


Snapshots are stored separately from the aggregate events, but snapshot objects are
implemented as a kind of domain event, and snapshotting uses the same mechanism
for storing snapshots as for storing aggregate events. When snapshotting is enabled,
the application object attribute ``snapshots`` is an event store dedicated to storing
snapshots. The snapshots can be retrieved from the snapshot store using the
:func:`~eventsourcing.persistence.EventStore.get` method. We can get the latest snapshot
by selecting in descending order with a limit of 1.

.. code-block:: python

    snapshots = application.snapshots.get(world_id, desc=True, limit=1)

    snapshots = list(snapshots)
    assert len(snapshots) == 1, len(snapshots)
    snapshot = snapshots[0]

    assert snapshot.originator_id == world_id
    assert snapshot.originator_version == 4

When snapshotting is enabled, the application repository looks for snapshots in this way.
If a snapshot is found by the aggregate repository when retrieving an aggregate,
then only the snapshot and subsequent aggregate events will be retrieved and used
to reconstruct the state of the aggregate.

Automatic snapshotting
----------------------

Automatic snapshotting of aggregates at regular intervals can be enabled
by setting the application class attribute 'snapshotting_intervals'. The
'snapshotting_intervals' should be a mapping of aggregate classes to integers
which represent the snapshotting interval. When aggregates are saved, snapshots
will be taken if the version of aggregate coincides with the specified interval.
The example below demonstrates this by extending the ``Worlds`` application class
with ``World`` aggregates snapshotted every 2 events.

.. code-block:: python

    class WorldsWithAutomaticSnapshotting(Worlds):
        snapshotting_intervals = {World: 2}


    application = WorldsWithAutomaticSnapshotting()

    world_id = application.create_world()

    application.make_it_so(world_id, "dinosaurs")
    application.make_it_so(world_id, "trucks")
    application.make_it_so(world_id, "internet")

    snapshots = application.snapshots.get(world_id)
    snapshots = list(snapshots)

    assert len(snapshots) == 2

    assert snapshots[0].originator_id == world_id
    assert snapshots[0].originator_version == 2

    assert snapshots[1].originator_id == world_id
    assert snapshots[1].originator_version == 4

In practice, a suitable interval would most likely be larger than 2.
Perhaps more like 100. And 'snapshotting_intervals' would be defined
directly on your application class.


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
