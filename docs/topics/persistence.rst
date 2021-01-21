================================================
:mod:`eventsourcing.persistence` --- Persistence
================================================

This module provides a cohesive mechanism for storing domain events.

The entire mechanism is encapsulated by the library's
**event store** object class. An event store stores and retrieves
domain events. The event store uses a mapper to convert
domain events to stored events, and it uses a recorder
to insert stored events in a datastore.

A **mapper** converts domain event objects of various types to
stored event objects when domain events are stored in the event
store. It also converts stored events objects back to domain
event objects when domain events are retrieved from the event
store. A mapper uses an extensible **transcoder** that can be set up
with additional transcoding objects that serialise and deserialise
particular types of object, such as Python's :class:`~uuid.UUID`,
:class:`~datetime.datetime` and :class:`~decimal.Decimal` objects.
A mapper may use a compressor to compress and decompress the state
of stored event objects, and may use a cipher to encode and decode
the state of stored event objects. If both a compressor and a cipher
are being used by a mapper, the state of any stored event objects will
be compressed and then encoded when storing domain events, and will be
decoded and then decompressed when retrieving domain events.

A **recorder** inserts stored event objects in a datastore when domain
events are stored in an event store, and selects stored events from
a datastore when domain events are retrieved from an event store.
Depending on the type of the recorder it may be possible to select
the stored events as event notifications, and it may be possible
atomically to record tracking records along with the stored events,


Transcoder
==========

A transcoder is used by a `mapper <#mapper>`_ to serialise and deserialise
the state of domain model event objects. The state of domain model event object
is expected to be a Python :class:`dict`. The serialised state is a Python
:class:`bytes` object.

The library's :class:`~eventsourcing.persistence.Transcoder` class
can be constructed without any arguments.

.. code:: python

    from eventsourcing.persistence import Transcoder

    transcoder = Transcoder()

The ``transcoder`` object has methods :func:`~eventsourcing.persistence.Transcoder.encode`
and :func:`~eventsourcing.persistence.Transcoder.decode`  which are used to perform the
serialisation and deserialisation.

.. code:: python

    value = transcoder.encode({'a': 1})
    assert transcoder.decode(value) == {'a': 1}

The library's :class:`~eventsourcing.persistence.Transcoder` uses the Python
:mod:`json` module. And so, by default, only the object types supported by that module
can be encoded and decoded. The transcoder can be extended by registering transcodings
for the data types used in your domain model. The transcoder method
:func:`~eventsourcing.persistence.Transcoder.register` is used to register individual
transcodings.


Transcodings
============

In order to encode and decode other types of object, custom transcodings need
to be defined, and then registered with the `transcoder <#transcoder>`_ using
the transcoder object's
:func:`~eventsourcing.persistence.Transcoder.register` method.
A transcoding will encode an instance of a non-basic type of object into
another type of object that can be encoded by the transcoder, and will
decode that object into the original type of object. This makes it possible
to transcode custom types, including custom types that contain custom types.

The library includes a limited collection of custom transcoding objects. For
example, the library's :class:`~eventsourcing.persistence.UUIDAsHex` class
transcodes a Python :class:`~uuid.UUID` objects as a hexadecimal string.

.. code:: python

    from uuid import uuid4

    from eventsourcing.persistence import UUIDAsHex

    transcoding = UUIDAsHex()

    id1 = uuid4()
    data = transcoding.encode(id1)
    assert transcoding.decode(data) == id1


Similarly, the library's :class:`~eventsourcing.persistence.DatetimeAsISO` class
transcodes Python :class:`~datetime.datetime` objects as ISO strings. The class
:class:`~eventsourcing.persistence.DecimalAsStr` transcodes Python :class:`~decimal.Decimal`
objects as decimal strings.

.. code:: python

    from datetime import datetime
    from decimal import Decimal

    from eventsourcing.persistence import (
        DatetimeAsISO,
        DecimalAsStr,
    )

    transcoding = DatetimeAsISO()
    datetime1 = datetime(2021, 12, 31, 23, 59, 59)
    value = transcoding.encode(datetime1)
    assert transcoding.decode(value) == datetime1


    transcoding = DecimalAsStr()
    decimal1 = Decimal("1.2345")
    value = transcoding.encode(decimal1)
    assert transcoding.decode(value) == decimal1


These transcodings can be registered with the transcoder.

.. code:: python

    transcoder.register(UUIDAsHex())
    transcoder.register(DatetimeAsISO())
    transcoder.register(DecimalAsStr())

    data = transcoder.encode(id1)
    assert transcoder.decode(data) == id1

    data = transcoder.encode(datetime1)
    assert transcoder.decode(data) == datetime1

    data = transcoder.encode(decimal1)
    assert transcoder.decode(data) == decimal1


Trying to transcode an unsupported type will result in a Python :class:`TypeError`.

.. code:: python

    from datetime import date

    date1 = date(2021, 12, 31)
    try:
        data = transcoder.encode(date1)
    except TypeError:
        pass
    else:
        raise Exception("shouldn't get here")


The library's abstract base class :class:`~eventsourcing.persistence.Transcoding`
can be subclassed to define custom transcodings for other object types.

.. code:: python

    from eventsourcing.persistence import Transcoding
    from typing import Union


    class DateAsISO(Transcoding):
        type = date
        name = "date_iso"

        def encode(self, obj: date) -> str:
            return obj.isoformat()

        def decode(self, data: str) -> date:
            return date.fromisoformat(data)


    transcoder.register(DateAsISO())

    data = transcoder.encode(date1)
    assert transcoder.decode(data) == date1

Please note, due to the way the Python :mod:`json` module works, it isn't
currently possible to transcode subclasses of the basic Python types that
are supported by default, such as :class:`dict`, :class:`list`, :class:`tuple`,
:class:`str`, :class:`int`, :class:`float`, and :class:`bool`.


Stored event objects
====================

A stored event object is a common object type that can be used to
represent domain event objects of different types. By using a
common object for the representation of different types of
domain events objects, the domain event objects can be stored
and retrieved in a standard way.

The library's :class:`~eventsourcing.persistence.StoredEvent` class
is a Python frozen dataclass that can be used to hold information
about a domain event object between it being serialised and being
recorded in a datastore, and between it be retrieved from a datastore
from an aggregate sequence and being deserialised as a domain event object.

.. code:: python

    from uuid import uuid4

    from eventsourcing.persistence import StoredEvent

    stored_event = StoredEvent(
        originator_id=uuid4(),
        originator_version=1,
        state="{}",
        topic="eventsourcing.model:DomainEvent",
    )


Mapper
======

A mapper maps between domain event objects and stored event objects. It brings
together a `transcoder <#transcoder>`_, and optionally a `cipher <#encryption>`_
and a `compressor <#compression>`_. It is used by an `event store <#event-store>`_.

The library's :class:`~eventsourcing.persistence.Mapper` class
must be constructed with a `transcoder <#transcoder>`_ object.

.. code:: python

    from eventsourcing.persistence import Mapper

    mapper = Mapper(transcoder=transcoder)

The :func:`~eventsourcing.persistence.Mapper.from_domain_event` method of the
``mapper`` object converts :class:`~eventsourcing.domain.DomainEvent` objects to
:class:`~eventsourcing.persistence.StoredEvent` objects.

.. code:: python

    from eventsourcing.domain import DomainEvent, TZINFO

    domain_event1 = DomainEvent(
        originator_id = id1,
        originator_version = 1,
        timestamp = datetime.now(tz=TZINFO),
    )

    stored_event1 = mapper.from_domain_event(domain_event1)
    assert isinstance(stored_event1, StoredEvent)


The :func:`~eventsourcing.persistence.Mapper.to_domain_event` method of the
``mapper`` object converts :class:`~eventsourcing.persistence.StoredEvent` objects to
:class:`~eventsourcing.domain.DomainEvent` objects.

.. code:: python

    assert mapper.to_domain_event(stored_event1) == domain_event1


Encryption
==========

Using a cryptographic cipher with your mapper will make the state of your application encrypted
"at rest" and "on the wire".

Without encryption, the state of the domain event will be visible in the
recorded stored events in your database. For example, the ``timestamp``
of the domain event in the example above (``domain_event1``) is visible
in the stored event (``stored_event1``).

.. code:: python

    assert domain_event1.timestamp.isoformat() in str(stored_event1.state)


The library's :class:`~eventsourcing.cipher.AESCipher` class can
be used to cryptographically encode and decode the state of stored
events. It must be constructed with a cipher key. The class method
:func:`~eventsourcing.cipher.AESCipher.create_key` can be used to
generate a cipher key. The AES cipher key must be either 16, 24, or
32 bytes long. Please note, the same cipher key must be used to
decrypt stored events as that which was used to encrypt stored events.

.. code:: python

    from eventsourcing.cipher import AESCipher

    key = AESCipher.create_key(num_bytes=32) # 16, 24, or 32
    cipher = AESCipher(cipher_key=key)

    mapper = Mapper(
        transcoder=transcoder,
        cipher=cipher,
    )

    stored_event1 = mapper.from_domain_event(domain_event1)
    assert isinstance(stored_event1, StoredEvent)
    assert mapper.to_domain_event(stored_event1) == domain_event1

With encryption, the state of the domain event will not be visible in the
stored event. This feature can be used to implement "application-level
encryption" in an event-sourced application.

.. code:: python

    assert domain_event1.timestamp.isoformat() not in str(stored_event1.state)


Compression
===========

A compressor can be used to reduce the size of stored events.

The Python :mod:`zlib` module can be used to compress and decompress
the state of stored events. The size of the state of a compressed
and encrypted stored event will be less than or equal to the size of
the state of a stored event that is encrypted but not compressed.

.. code:: python

    import zlib

    mapper = Mapper(
        transcoder=transcoder,
        cipher=cipher,
        compressor=zlib,
    )

    stored_event2 = mapper.from_domain_event(domain_event1)
    assert mapper.to_domain_event(stored_event2) == domain_event1

    assert len(stored_event2.state) <= len(stored_event1.state)


Event notification objects
==========================

Event notifications are used to propagate the state of an event
sourced application in a reliable way. The stored events can be
positioned in a "total order" by giving each a new domain event
a notification ID that is higher that any previously recorded event.
By recording the domain events atomically with their notification IDs,
there will never be a domain event that is not available to be passed
as a message across a network, and there will never be a message
passed across a network that doesn't correspond to a recorded event.
This solves the "dual writing" problem that occurs when separately
a domain model is updated and then a message is put on a message queue.

The library's :class:`~eventsourcing.persistence.Notification` class
is a Python frozen dataclass that can be used to hold information
about a domain event object when being transmitted as an item in a
section of a `notification log <application.html#notification-log>`_.
It will be returned when selecting event notifications from a
`recorder <#recorder>`_, and presented in an application by a
`notification log <applications.html#notification-log>`_.

.. code:: python

    from uuid import uuid4

    from eventsourcing.persistence import Notification

    stored_event = Notification(
        id=123,
        originator_id=uuid4(),
        originator_version=1,
        state="{}",
        topic="eventsourcing.model:DomainEvent",
    )


Tracking objects
================

A tracking object can be used to encapsulate the position of
an event notification in an upstream application's notification
log. A tracking object can be passed into a process recorder along
with new stored event objects, and recorded atomically with those
objects. By ensuring the uniqueness of recorded tracking objects,
we can ensure that a domain event notification is never processed
twice. By recording the position of the last event notification that
has been processed, we can ensure to resume processing event notifications
at the correct position. This constructs "exactly once" semantics
when processing event notifications, by solving the "dual writing"
problem that occurs when separately an event notification is consumed
from a message queue with updates made to materialized view, and then
an acknowledgement is sent back to the message queue.

The library's :class:`~eventsourcing.persistence.Tracking` class
is a Python frozen dataclass that can be used to hold the notification
ID of a notification that has been processed.

.. code:: python

    from uuid import uuid4

    from eventsourcing.persistence import Tracking

    tracking = Tracking(
        notification_id=123,
        application_name='bounded_context1',
    )


Recorder
========

A recorder adapts a database management system for the purpose of
recording stored events. It is used by an `event store <#event-store>`_.

The library's :class:`~eventsourcing.persistence.Recorder` class
is an abstract base for concrete recorder classes that will insert
stored event objects in a particular datastore.

There are three flavours of recorder: "aggregate recorders"
are the simplest and simply store domain events in aggregate
sequences; "application recorders" extend aggregate recorders
by storing domain events with a total order; "process recorders"
extend application recorders by supporting the recording of
domain events atomically with "tracking" objects that record
the position in a total ordering of domain events that is
being processed. The "aggregate recorder" can be used for
storing snapshots.

The library includes concrete recorder classes for SQLite using
the Python :mod:`sqlite3` module, and for PostgreSQL using the
third party :mod:`psycopg2` module. The library also includes
recorder using "plain old Python objects" which provides
a fast in-memory alternative for rapid development of event
sourced applications.

.. code:: python

    from eventsourcing.sqlite import SQLiteAggregateRecorder
    from eventsourcing.sqlite import SQLiteApplicationRecorder
    from eventsourcing.sqlite import SQLiteProcessRecorder
    from eventsourcing.sqlite import SQLiteDatastore

    datastore = SQLiteDatastore(db_name=':memory:')
    aggregate_recorder = SQLiteAggregateRecorder(datastore, "snapshots")
    aggregate_recorder.create_table()

    application_recorder = SQLiteApplicationRecorder(datastore)
    application_recorder.create_table()

    datastore = SQLiteDatastore(db_name=':memory:')
    process_recorder = SQLiteProcessRecorder(datastore)
    process_recorder.create_table()


Event Store
===========

An event store provides a common interface for storing and retrieving
domain event objects. It combines a `mapper <#mapper>`_ and a `recorder <#recorder>`_,
so that domain event objects can be converted to stored event objects, and
then stored event objects can be recorded in a datastore.

The library's :class:`~eventsourcing.persistence.EventStore` class must
be constructed with a `recorder <#recorder`_ and a `mapper <#mapper>`_.

.. code:: python

    from eventsourcing.persistence import EventStore

    event_store = EventStore(
        recorder=application_recorder,
        mapper=mapper,
    )

    event_store.put([domain_event1])
    stored_events = list(event_store.get(id1))
    assert stored_events == [domain_event1]


Infrastructure Factory
======================

An infrastructure factory helps with the construction of the persistence objects mentioned
above. By reading and responding to particular environment variables, the persistence
infrastructure of an event-sourced application can be `easily configured in different ways
at different times <application.html#configuring-persistence>`_.

The library's :class:`~eventsourcing.persistence.InfrastructureFactory` class
is a base class for concrete infrastructure factories that help with the construction
of persistence objects that use a particular database in a particular way.

The class method :class:`~eventsourcing.persistence.InfrastructureFactory.construct`
will by default construct the library's "plain old Python objects" persistence infrastructure.

.. code:: python

    from eventsourcing.persistence import InfrastructureFactory

    factory = InfrastructureFactory.construct(application_name='')

    recorder = factory.application_recorder()
    mapper = factory.mapper(transcoder=transcoder)
    event_store = factory.event_store(
        mapper=mapper,
        recorder=recorder,
    )

    event_store.put([domain_event1])
    stored_events = list(event_store.get(id1))
    assert stored_events == [domain_event1]


SQLite
======

The module :mod:`eventsourcing.sqlite` supports storing events in SQLite.

The SQLite :class:`eventsourcing.sqlite:Factory` uses environment variables
``'SQLITE_DBNAME'`` and ``'DO_CREATE_TABLE'``.

.. code:: python

    import os

    os.environ['INFRASTRUCTURE_FACTORY'] = 'eventsourcing.sqlite:Factory'
    os.environ['SQLITE_DBNAME'] = ':memory:'
    os.environ['DO_CREATE_TABLE'] = 'y'

    factory = InfrastructureFactory.construct(application_name='')

    recorder = factory.application_recorder()
    mapper = factory.mapper(transcoder=transcoder)
    event_store = factory.event_store(
        mapper=mapper,
        recorder=recorder,
    )

    event_store.put([domain_event1])
    stored_events = list(event_store.get(id1))
    assert stored_events == [domain_event1]


PostgreSQL
==========

The module :mod:`eventsourcing.postgres` supports storing events in PostgresSQL.

The SQLite :class:`eventsourcing.sqlite:Factory` uses environment variables
``'POSTGRES_DBNAME'``, ``'POSTGRES_HOST'``, ``'POSTGRES_USER'``,
``'POSTGRES_PASSWORD'``, and ``'DO_CREATE_TABLE'``.


.. code:: python

    import os

    os.environ['INFRASTRUCTURE_FACTORY'] = 'eventsourcing.postgres:Factory'
    os.environ["POSTGRES_DBNAME"] = "eventsourcing"
    os.environ["POSTGRES_HOST"] = "127.0.0.1"
    os.environ["POSTGRES_USER"] = "eventsourcing"
    os.environ["POSTGRES_PASSWORD"] = "eventsourcing"
    os.environ['DO_CREATE_TABLE'] = 'y'

..
    from eventsourcing.tests.test_postgres import drop_postgres_table
    factory = InfrastructureFactory.construct(application_name='')
    drop_postgres_table(factory.datastore, "stored_events")


.. code:: python

    factory = InfrastructureFactory.construct(application_name='')

    recorder = factory.application_recorder()
    mapper = factory.mapper(transcoder=transcoder)
    event_store = factory.event_store(
        mapper=mapper,
        recorder=recorder,
    )

    event_store.put([domain_event1])
    stored_events = list(event_store.get(id1))
    assert stored_events == [domain_event1]


Classes
=======

.. automodule:: eventsourcing.persistence
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

.. automodule:: eventsourcing.popo
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__

.. automodule:: eventsourcing.sqlite
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__

.. automodule:: eventsourcing.postgres
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__
