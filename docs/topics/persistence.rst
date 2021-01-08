===========
Persistence
===========

The library's persistence module provides a cohesive
mechanism for storing domain events.

The entire mechanism is encapsulated by the library's
event store object class. An event store stores and retrieves
domain events. The event store uses a mapper to convert
domain events to stored events, and it uses a recorder
to insert stored events in a datastore.

A mapper converts domain event objects of various types to
stored event objects when domain events are stored in the event
store. It also converts stored events objects back to domain
event objects when domain events are retrieved from the event
store. A mapper uses an extensible transcoder that can be set up
with additional transcoding objects that serialise and deserialise
particular types of object, such as Python's ``UUID``, ``datatime``
and ``Decimal`` objects. A mapper may use a compressor to compress
and decompress the state of stored event objects, and may use a
cipher to encode and decode the state of stored event objects. If both
a compressor and a cipher are being used by a mapper, the state of any
stored event objects will be compressed and then encoded when storing
domain events, and will be decoded and then decompressed when retrieving
domain events.

A recorder inserts stored event objects in a datastore when domain
events are stored in an event store, and selects stored events from
a datastore when domain events are retrieved from an event store.
Depending on the type of the recorder
it may be possible to select the stored events as event notifications,
and
it may be possible atomically to record tracking records along with the stored events,

.. contents:: :local:


Stored event objects
====================

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


Event notification objects
==========================

The library's :class:`~eventsourcing.persistence.Notification` class
is a Python frozen dataclass that can be used to hold information
about a domain event object between it be selected from a datastore
from the total ordering of domain events in an application
and being transmitted as an item in a section of a notification log.

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

The library's :class:`~eventsourcing.persistence.Tracking` class
is a Python frozen dataclass that can be used to hold information
about the position of a notification in a total ordering of domain
events in an application.

.. code:: python

    from uuid import uuid4

    from eventsourcing.persistence import Tracking

    tracking = Tracking(
        notification_id=123,
        application_name='bounded_context1',
    )


Transcoder
==========

The library's :class:`~eventsourcing.persistence.Transcoder` class
can be constructed without any arguments.

.. code:: python

    from eventsourcing.persistence import Transcoder

    transcoder = Transcoder()

The ``transcoder`` object has methods ``encode()`` and ``decode()``
that will serialise and deserialise objects of different types to
JSON objects.

.. code:: python

    value = transcoder.encode(1)
    assert transcoder.decode(value) == 1

    value = transcoder.encode('a')
    assert transcoder.decode(value) == 'a'

    value = transcoder.encode({'a': 1})
    assert transcoder.decode(value) == {'a': 1}

    value = transcoder.encode([1, 2, 3])
    assert transcoder.decode(value) == [1, 2, 3]

The transcoder uses the Python ``json`` module, and so
by default only the object types supported by that module
can be encoded and decoded.
In order to encode and decode other types of object, custom
transcodings need to be registered with the transcoder
using the transcoder object's ``register()`` method.

The library includes a limited collection of custom transcoding
objects. For example, the library's
:class:`~eventsourcing.persistence.UUIDAsHex` class
transcodes Python ``UUID`` objects as hexadecimal strings.

.. code:: python

    from eventsourcing.persistence import UUIDAsHex

    transcoder.register(UUIDAsHex())

    id1 = uuid4()
    value = transcoder.encode(id1)
    assert transcoder.decode(value) == id1


Similarly, the library's :class:`~eventsourcing.persistence.DatetimeAsISO` class
transcodes Python ``datatime`` objects as ISO strings, and
the class :class:`~eventsourcing.persistence.DecimalAsStr`
transcodes Python ``Decimal`` objects as decimal strings.

.. code:: python

    from eventsourcing.persistence import (
        DatetimeAsISO,
        DecimalAsStr,
    )

    transcoder.register(DatetimeAsISO())
    transcoder.register(DecimalAsStr())


    from datetime import datetime

    datetime1 = datetime(2021, 12, 31, 23, 59, 59)
    value = transcoder.encode(datetime1)
    assert transcoder.decode(value) == datetime1


    from decimal import Decimal

    decimal1 = Decimal("1.2345")
    value = transcoder.encode(decimal1)
    assert transcoder.decode(value) == decimal1

Trying to transcode an unsupported type will result in a ``TypeError``.

.. code:: python

    from datetime import date

    date1 = date(2021, 12, 31)
    try:
        value = transcoder.encode(date1)
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

        def encode(self, o: date) -> str:
            return o.isoformat()

        def decode(self, d: Union[str, dict]) -> date:
            assert isinstance(d, str)
            return date.fromisoformat(d)


    transcoder.register(DateAsISO())

    value = transcoder.encode(date1)
    assert transcoder.decode(value) == date1


Mapper
======

The library's :class:`~eventsourcing.persistence.Mapper` class
must be constructed with a ``transcoder`` object.

.. code:: python

    from eventsourcing.persistence import Mapper

    mapper = Mapper(transcoder=transcoder)

The ``from_domain_event()`` method of the ``mapper`` object converts
:class:`~eventsourcing.domain.DomainEvent` objects to
:class:`~eventsourcing.persistence.StoredEvent` objects.

.. code:: python

    from eventsourcing.domain import DomainEvent

    domain_event1 = DomainEvent(
        originator_id = id1,
        originator_version = 1,
        timestamp = datetime.now(),
    )

    stored_event1 = mapper.from_domain_event(domain_event1)
    assert isinstance(stored_event1, StoredEvent)


The ``to_domain_event()`` method of the ``mapper`` object converts
:class:`~eventsourcing.persistence.StoredEvent` objects to
:class:`~eventsourcing.domain.DomainEvent` objects.

.. code:: python

    assert mapper.to_domain_event(stored_event1) == domain_event1

Without encryption, the state of the domain event will be visible
in the stored event.

.. code:: python

    assert domain_event1.timestamp.isoformat() in str(stored_event1.state)


The library's :class:`~eventsourcing.cipher.AESCipher` class can
be used to cryptographically encode and decode the state of stored
events. It must be constructed with a cipher key. The class method
``create_key()`` can be used to generate a cipher key. The AES cipher
key must be either 16, 24, or 32 bytes long. Please note, the same
cipher key must be used to decrypt stored events as that which was
used to encrypt stored events.

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
encryption" in an event sourced application.

.. code:: python

    assert domain_event1.timestamp.isoformat() not in str(stored_event1.state)

The Python ``zlib`` module can be used to compress and decompress
the state of stored events. The size of the state of a compressed
and encrypted stored event will be less than size of the state of
a stored event that is encrypted but not compressed.

.. code:: python

    import zlib

    mapper = Mapper(
        transcoder=transcoder,
        cipher=cipher,
        compressor=zlib,
    )

    stored_event2 = mapper.from_domain_event(domain_event1)
    assert mapper.to_domain_event(stored_event2) == domain_event1

    assert len(stored_event2.state) < len(stored_event1.state)


Recorder
========

The library's :class:`~eventsourcing.persistence.Recorder` class
is an abstract base for concrete recorder classes that insert
stored event objects in a datastore.

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
the Python ``sqlite3`` module, and for PostgreSQL using the
third-part ``psycopg2`` module. The library also includes
recorder using "plain old Python objects" which provides
a fast in-memory alternative for rapid development of event
sourced applications.

.. code:: python

    from eventsourcing.sqlite import SQLiteAggregateRecorder
    from eventsourcing.sqlite import SQLiteApplicationRecorder
    from eventsourcing.sqlite import SQLiteProcessRecorder
    from eventsourcing.sqlite import SQLiteDatastore

    datastore = SQLiteDatastore(db_name=':memory:')

    aggregate_recorder = SQLiteApplicationRecorder(datastore)
    aggregate_recorder.create_table()

    application_recorder = SQLiteApplicationRecorder(datastore)
    application_recorder.create_table()

    process_recorder = SQLiteProcessRecorder(datastore)
    process_recorder.create_table()


Event Store
===========

The library's :class:`~eventsourcing.persistence.EventStore`
class...

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

With "plain old Python objects" (the default)....

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


With SQLite....

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


With PostgreSQL....

.. code:: python

    import os

    os.environ['INFRASTRUCTURE_FACTORY'] = 'eventsourcing.postgres:Factory'
    os.environ["POSTGRES_DBNAME"] = "eventsourcing"
    os.environ["POSTGRES_HOST"] = "127.0.0.1"
    os.environ["POSTGRES_USER"] = "eventsourcing"
    os.environ["POSTGRES_PASSWORD"] = "eventsourcing"
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
