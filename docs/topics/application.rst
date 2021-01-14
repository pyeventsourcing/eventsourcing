=================================================
:mod:`eventsourcing.application` --- Applications
=================================================


This module helps with developing event sourced applications.

There is a base class for event sourced **application** object. There is also
a **repository** for class that is used to obtain already existing aggregates,
and a **notification log** class that is used to propagate the state of
the application as a sequence of domain event notifications.

Application layer in DDD
========================


In *Domain-Driven Design*, the application layer combines the
:doc:`domain </topics/domain>` and :doc:`infrastructure </topics/persistence>`
layers.

Generally speaking, the application layer implements commands which change the
state of the application, and queries which present the state of the application.
The application's command and queries are used by an interface layer. By keeping
the business logic of the application in the application and domain layers,
different interfaces can be developed for different technologies without
duplicating business logic.


Application object
==================

The library's :class:`~eventsourcing.application.Application` object class can be
subclassed to develop an event sourced application.

The general idea is to name your application object classes after the bounded
context supported by its domain model, and the define command and query methods
that allow interfaces to create, read, update and delete domain model aggregates.

The application's ``save()`` method is used to update the recorded state of the application's
`aggregates <domain.html#event-sourced-aggregates>`_. The aggregate's ``collect()``
method is used to collect pending events, which are stored by calling the
``put()`` method of application's `event store <persistence.html#event-store>`_.

The application's ``repository`` attribute has an `event sourced repository <#repository>`_. The
repository ``get()`` method is used by application command and query methods to
obtain already existing event sourced aggregates.

The application's ``log`` attribute has an `local notification log <#notification-log>`_.
The notification log can be used to propagate the state of the application as
a sequence of domain event notifications.

The application's ``take_snapshot()`` method can be used to take snapshots of existing
aggregates.

Basic example
-------------

In the example below, the ``Worlds`` application extends the library's
application object class. The ``World`` aggregate is defined and discussed
in the :doc:`domain module documentation </topics/domain>`.

The application's command method ``create_world()`` creates and saves
new ``World`` aggregates, returning a new ``world_id`` that can be used
to identify the aggregate on subsequence method calls.
It saves the new aggregate by calling the base class ``save()`` method.

The application's command method ``make_it_so()`` obtains an existing ``World``
aggregate from the repository. It calls the ``World`` aggregate command method
``make_it_so()``, and then saves the aggregate by calling the application's
``save()`` method.

The application's query method ``get_world_history()`` presents the current
history of an existing aggregate.

.. code:: python

    from typing import List
    from uuid import UUID

    from eventsourcing.application import Application


    class WorldsApplication(Application):

        def create_world(self) -> UUID:
            world = World.create()
            self.save(world)
            return world.uuid

        def make_it_so(self, world_id: UUID, what: str):
            world = self.repository.get(world_id)
            world.make_it_so(what)
            self.save(world)

        def get_world_history(self, world_id: UUID) -> List[str]:
            world = self.repository.get(world_id)
            return list(world.history)


..
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


In the example below, an instance of the ``Worlds`` application is constructed.
A new ``World`` aggregate is created by calling the ``create_world()`` method.
Three items are added to its history: 'dinosaurs', 'trucks', and 'internet' by
calling the ``make_it_so()`` application command with the ``world_id`` aggregate
ID. The history of the aggregate is obtained when the ``get_world_history()``
method is called.


.. code:: python

    application = WorldsApplication()

    world_id = application.create_world()

    application.make_it_so(world_id, 'dinosaurs')
    application.make_it_so(world_id, 'trucks')
    application.make_it_so(world_id, 'internet')

    history = application.get_world_history(world_id)
    assert history[0] == 'dinosaurs'
    assert history[1] == 'trucks'
    assert history[2] == 'internet'


Repository
==========

Todo: more about object class :class:`~eventsourcing.application.Repository`.

Notification log
================

There are now four domain event notifications in the application's
notification ``log``. The application's notificaiton log is an
instance of the library's :class:`~eventsourcing.application.LocalNotificationLog` class.

The notification log presents linked sections of event notifications. The sections
are instances of the library's :class:`~eventsourcing.application.Section` class.
The attribute ``items`` is a list of `event notification
objects <persistence.html#event-notification-objects>`_.


.. code:: python

    from eventsourcing.persistence import Notification


    section = application.log['1,10']

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

    assert 'Aggregate.Created' in section.items[0].topic
    assert 'World.SomethingHappened' in section.items[1].topic
    assert 'World.SomethingHappened' in section.items[2].topic
    assert 'World.SomethingHappened' in section.items[3].topic

    assert b'dinosaurs' in section.items[1].state
    assert b'trucks' in section.items[2].state
    assert b'internet' in section.items[3].state


The application method ``take_snapshot()`` can be used to create
a snapshot of the state of an aggregate. The ID and version of an
aggregate to be snapshotted must be passed when calling this method.

To enable the snapshotting functionality, the environment variable
``IS_SNAPSHOTTING_ENABLED`` must be set to a valid "true"  value. The ``distutils.utils`` function
``strtobool()`` is used to interpret the value of this environment variable,
so that strings 'y', 'yes', 't', 'true', 'on', and '1' are considered to be
"true" values, 'n', 'no', 'f', 'false', 'off', '0' are considered to be
"false" values, and other values are considered to be invalid. The default
is for the application's snapshotting functionality not to be enabled.

.. code:: python

    import os

    os.environ['IS_SNAPSHOTTING_ENABLED'] = 'y'
    application = WorldsApplication()

    world_id = application.create_world()

    application.make_it_so(world_id, 'dinosaurs')
    application.make_it_so(world_id, 'trucks')
    application.make_it_so(world_id, 'internet')

    application.take_snapshot(world_id, version=4)


Configuring persistence
=======================

By default, the application object uses the `"Plain Old Python Object"
infrastructure <persistence.html#infrastructure-factory>`_

To use other persistence infrastructure,
set the environment variable ``INFRASTRUCTURE_FACTORY`` to the topic of
another infrastructure factory. Often using other persistence infrastructure
will involve setting other environment variables to condition access to a real
database.

In the example below, the library's SQLite infrastructure factory is used.
In the case of the library's SQLite factory, the environment variables
``SQLITE_DBNAME`` and ``DO_CREATE_TABLE`` must be set.

.. code:: python


    from tempfile import NamedTemporaryFile

    tmpfile = NamedTemporaryFile(suffix="_eventsourcing_test.db")
    tmpfile.name

    os.environ['INFRASTRUCTURE_FACTORY'] = 'eventsourcing.sqlite:Factory'
    os.environ['SQLITE_DBNAME'] = tmpfile.name
    os.environ['DO_CREATE_TABLE'] = 'yes'
    application = WorldsApplication()

    world_id = application.create_world()

    application.make_it_so(world_id, 'dinosaurs')
    application.make_it_so(world_id, 'trucks')
    application.make_it_so(world_id, 'internet')

    application.take_snapshot(world_id, version=2)


By using a file on disk, the named temporary file ``tmpfile`` above,
the state of the application will endure after the application has
been reconstructed. The database table only needs to be created once,
and so when creating an application for an already existing database
the ``DO_CREATE_TABLE`` value must be a "false" value.


.. code:: python

    os.environ['INFRASTRUCTURE_FACTORY'] = 'eventsourcing.sqlite:Factory'
    os.environ['DO_CREATE_TABLE'] = 'no'
    application = WorldsApplication()

    history = application.get_world_history(world_id)
    assert history[0] == 'dinosaurs'
    assert history[1] == 'trucks'
    assert history[2] == 'internet'


Registering custom transcodings
===============================

The application method ``register_transcodings()`` can
be extended to register custom transcodings for custom
value objects used in your application's domain events.

.. code:: python

    from datetime import date
    from typing import Union

    from eventsourcing.persistence import Transcoder, Transcoding


    class MyApplication(Application):

        def register_transcodings(self, transcoder: Transcoder):
            super().register_transcodings(transcoder)
            transcoder.register(DateAsISO)


    class DateAsISO(Transcoding):
        type = date
        name = "date_iso"

        def encode(self, o: date) -> str:
            return o.isoformat()

        def decode(self, d: Union[str, dict]) -> date:
            assert isinstance(d, str)
            return date.fromisoformat(d)


Encryption and compression
==========================

To enable encryption and compression, set the
environment variables 'CIPHER_TOPIC', 'CIPHER_KEY',
and 'COMPRESSOR_TOPIC'. You can use the static method
``AESCipher.create_key()`` to generate a cipher key.

.. code:: python

    import os

    from eventsourcing.cipher import AESCipher

    # Generate a cipher key (keep this safe).
    cipher_key = AESCipher.create_key(num_bytes=32)

    # Configure cipher key.
    os.environ['CIPHER_KEY'] = cipher_key
    # Configure cipher topic.
    os.environ['CIPHER_TOPIC'] = "eventsourcing.cipher:AESCipher"
    # Configure compressor topic.
    os.environ['COMPRESSOR_TOPIC'] = "zlib"



..
    #Todo: Register custom transcodings on transcoder.
    #Todo: Show how to use UUID5.
    #Todo: Show how to use ORM objects for read model.

Classes
=======

.. automodule:: eventsourcing.application
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__
