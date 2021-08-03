====================================================
:mod:`~eventsourcing.persistence` --- Infrastructure
====================================================

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

.. _Transcoder:

Transcoder
==========

A transcoder is used by a :ref:`mapper<Mapper>` to serialise and deserialise
the state of domain model event objects.

The library's :class:`~eventsourcing.persistence.JSONTranscoder` class
can be constructed without any arguments.

.. code:: python

    from eventsourcing.persistence import JSONTranscoder

    transcoder = JSONTranscoder()

The :data:`transcoder` object has methods :func:`~eventsourcing.persistence.JSONTranscoder.encode`
and :func:`~eventsourcing.persistence.JSONTranscoder.decode`  which are used to perform the
serialisation and deserialisation. The serialised state is a Python :class:`bytes` object.

.. code:: python

    data = transcoder.encode({"a": 1})
    copy = transcoder.decode(data)
    assert copy == {"a": 1}

The library's :class:`~eventsourcing.persistence.JSONTranscoder` uses the Python
:mod:`json` module. And so, by default, only the basic object types supported by that
module can be encoded and decoded. The transcoder can be extended by registering
transcodings for the other types of object used in your domain model's event objects.
A transcoding will convert other types of object to a representation of the non-basic
type of object that uses the basic types that are supported. The transcoder method
:func:`~eventsourcing.persistence.Transcoder.register` is used to register
individual transcodings with the transcoder.

.. _Transcodings:

Transcodings
============

In order to encode and decode non-basic types of object that are not supported by
the transcoder by default, custom transcodings need to be defined in code and
registered with the :ref:`transcoder<Transcoder>` using the transcoder object's
:func:`~eventsourcing.persistence.Transcoder.register` method. A transcoding
will encode an instance of a non-basic type of object that cannot by default be
encoded by the transcoder into a basic type of object that can be encoded by the
transcoder, and will decode that representation into the original type of object.
This makes it possible to transcode custom value objects, including custom types
that contain custom types. The transcoder works recursively through the object
and so included custom types do not need to be encoded by the transcoder, but
will be converted subsequently.

The library includes a limited collection of custom transcoding objects. For
example, the library's :class:`~eventsourcing.persistence.UUIDAsHex` class
transcodes a Python :class:`~uuid.UUID` objects as a hexadecimal string.

.. code:: python

    from uuid import uuid4

    from eventsourcing.persistence import UUIDAsHex

    transcoding = UUIDAsHex()

    id1 = uuid4()
    data = transcoding.encode(id1)
    copy = transcoding.decode(data)
    assert copy == id1


The library's :class:`~eventsourcing.persistence.DatetimeAsISO` class
transcodes Python :class:`~datetime.datetime` objects as ISO strings.

.. code:: python

    from datetime import datetime

    from eventsourcing.persistence import (
        DatetimeAsISO,
    )

    transcoding = DatetimeAsISO()

    datetime1 = datetime(2021, 12, 31, 23, 59, 59)
    data = transcoding.encode(datetime1)
    copy = transcoding.decode(data)
    assert copy == datetime1


The library's :class:`~eventsourcing.persistence.DecimalAsStr` class
transcodes Python :class:`~decimal.Decimal` objects as decimal strings.

.. code:: python

    from decimal import Decimal

    from eventsourcing.persistence import (
        DecimalAsStr,
    )

    transcoding = DecimalAsStr()

    decimal1 = Decimal("1.2345")
    data = transcoding.encode(decimal1)
    copy = transcoding.decode(data)
    assert copy == decimal1


Transcodings are registered with the transcoder using the transcoder object's
:func:`~eventsourcing.persistence.Transcoder.register` method.

.. code:: python

    transcoder.register(UUIDAsHex())
    transcoder.register(DatetimeAsISO())
    transcoder.register(DecimalAsStr())

    data = transcoder.encode(id1)
    copy = transcoder.decode(data)
    assert copy == id1

    data = transcoder.encode(datetime1)
    copy = transcoder.decode(data)
    assert copy == datetime1

    data = transcoder.encode(decimal1)
    copy = transcoder.decode(data)
    assert copy == decimal1


Attempting to serialize an unsupported type will result in a Python :class:`TypeError`.

.. code:: python

    from datetime import date

    date1 = date(2021, 12, 31)
    try:
        data = transcoder.encode(date1)
    except TypeError as e:
        assert e.args[0] == (
            "Object of type <class 'datetime.date'> is not serializable. "
            "Please define and register a custom transcoding for this type."
        )
    else:
        raise AssertionError("TypeError not raised")


Attempting to deserialize an unsupported type will also result in a Python :class:`TypeError`.

.. code:: python

    try:
        JSONTranscoder().decode(data)
    except TypeError as e:
        assert e.args[0] == (
            "Data serialized with name 'decimal_str' is not deserializable. "
            "Please register a custom transcoding for this type."
        )
    else:
        raise AssertionError("TypeError not raised")


The library's abstract base class :class:`~eventsourcing.persistence.Transcoding`
can be subclassed to define custom transcodings for other object types. To define
a custom transcoding, simply subclass this base class, assign to the class attribute
:data:`type` the class transcoded type, and assign a string to the class attribute
:data:`name`. Then define an :func:`~eventsourcing.persistence.Transcoding.encode`
method that converts an instance of that type to a representation that uses a basic
type, and a :func:`~eventsourcing.persistence.Transcoding.decode` method that will
convert that representation back to an instance of that type.

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
    copy = transcoder.decode(data)
    assert copy == date1


Please note, due to the way the Python :mod:`json` module works, it isn't
currently possible to transcode subclasses of the basic Python types that
are supported by default, such as :class:`dict`, :class:`list`, :class:`tuple`,
:class:`str`, :class:`int`, :class:`float`, and :class:`bool`. This behaviour
also means an encoded :class:`tuple` will be decoded as a :class:`list`.
This behaviour is coded in Python as C code, and can't be suspended without
avoiding the use of this C code and thereby incurring a performance penalty
in the transcoding of domain event objects.

.. code:: python

    data = transcoder.encode((1, 2, 3))
    copy = transcoder.decode(data)
    assert isinstance(copy, list)
    assert copy == [1, 2, 3]


Custom or non-basic types that contain other custom or non-basic types can be
supported in the transcoder by registering a transcoding for each non-basic type.
The transcoding for the type which contains non-basic types must return an object
that represents that type by involving the included non-basic objects, and this
representation will be subsequently transcoded by the transcoder using the applicable
transcoding for the included non-basic types. In the example below, :class:`SimpleCustomValue`
has a :class:`UUID` and a :class:`date` as its :data:`id` and :data:`data` attributes.
The transcoding for :class:`SimpleCustomValue` returns a Python :class:`dict` that includes
the non-basic :class:`UUID` and :class:`date` objects. The class :class:`ComplexCustomValue`
simply has a :class:`ComplexCustomValue` object as its :class:`value` attribute, and its
transcoding simply returns that object.

.. code:: python

    from uuid import UUID


    class SimpleCustomValue:
        def __init__(self, id: UUID, date: date):
            self.id = id
            self.date = date

        def __eq__(self, other):
            return (
                isinstance(other, SimpleCustomValue) and
                self.id == other.id and self.date == other.date
            )

    class ComplexCustomValue:
        def __init__(self, value: SimpleCustomValue):
            self.value = value

        def __eq__(self, other):
            return (
                isinstance(other, ComplexCustomValue) and
                self.value == other.value
            )


    class SimpleCustomValueAsDict(Transcoding):
        type = SimpleCustomValue
        name = "simple_custom_value"

        def encode(self, obj: SimpleCustomValue) -> dict:
            return {"id": obj.id, "date": obj.date}

        def decode(self, data: dict) -> SimpleCustomValue:
            assert isinstance(data, dict)
            return SimpleCustomValue(**data)


    class ComplexCustomValueAsDict(Transcoding):
        type = ComplexCustomValue
        name = "complex_custom_value"

        def encode(self, obj: ComplexCustomValue) -> SimpleCustomValue:
            return obj.value

        def decode(self, data: SimpleCustomValue) -> ComplexCustomValue:
            assert isinstance(data, SimpleCustomValue)
            return ComplexCustomValue(data)


The custom value object transcodings can be registered with the transcoder.

.. code:: python

    transcoder.register(SimpleCustomValueAsDict())
    transcoder.register(ComplexCustomValueAsDict())

We can now transcode an instance of :class:`ComplexCustomValueAsDict`.

.. code:: python

    obj1 = ComplexCustomValue(
        SimpleCustomValue(
            id=UUID("b2723fe2c01a40d2875ea3aac6a09ff5"),
            date=date(2000, 2, 20)
        )
    )

    data = transcoder.encode(obj1)
    copy = transcoder.decode(data)
    assert copy == obj1


As you can see from the bytes representation below, the transcoder puts the return value
of each transcoding's :func:`encode` method in a Python :class:`dict` that has two values
:data:`_data_` and :data:`_type_`. The :data:`_data_` value is the return value of the
transcoding's :func:`encode` method, and the :data:`_type_` value is the name of the
transcoding. For this reason, it is necessary to avoid defining model objects to have a
Python :class:`dict` that has only two attributes :data:`_data_` and :data:`_type_`, and
avoid defining transcodings that return such a thing.

.. code:: python

    expected_data = (
        b'{"_type_": "complex_custom_value", "_data_": {"_type_": '
        b'"simple_custom_value", "_data_": {"id": {"_type_": '
        b'"uuid_hex", "_data_": "b2723fe2c01a40d2875ea3aac6a09ff5"},'
        b' "date": {"_type_": "date_iso", "_data_": "2000-02-20"}'
        b'}}}'
    )
    assert data == expected_data


.. _Stored event objects:

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


.. _Mapper:

Mapper
======

A mapper maps between domain event objects and stored event objects. It brings
together a :ref:`transcoder<Transcoder>`, and optionally a :ref:`cipher<Encryption>`
and a :ref:`compressor<Compression>`. It is used by an :ref:`event store<Store>`.

The library's :class:`~eventsourcing.persistence.Mapper` class
must be constructed with a :ref:`transcoder<Transcoder>` object.

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


.. _Encryption:

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

The library's :class:`~eventsourcing.cipher.AESCipher` class uses the
`AES cipher <https://pycryptodome.readthedocs.io/en/stable/src/cipher/aes.html>`_
from the `PyCryptodome library <https://pycryptodome.readthedocs.io/en/stable/index.html>`_
in `GCM mode <https://pycryptodome.readthedocs.io/en/stable/src/cipher/modern.html#gcm-mode>`_.
AES is a very fast and secure symmetric block cipher, and is the de facto
standard for symmetric encryption. Galois/Counter Mode (GCM) is a mode of
operation for symmetric block ciphers that is designed to provide both data
authenticity and confidentiality, and is widely adopted for its performance.

The mapper expects an instance of the abstract base class :class:`~eventsourcing.cipher.Cipher`,
and :class:`~eventsourcing.cipher.AESCipher` implements this abstract base class,
so if you want to use another cipher strategy simply implement the base class.


.. _Compression:

Compression
===========

A compressor can be used to reduce the size of stored events.

The library's :class:`~eventsourcing.compressor.ZlibCompressor` class
can be used to compress and decompress the state of stored events. The
size of the state of a compressed and encrypted stored event will be
less than or equal to the size of the state of a stored event that is
encrypted but not compressed.

.. code:: python

    from eventsourcing.compressor import ZlibCompressor

    compressor = ZlibCompressor()

    mapper = Mapper(
        transcoder=transcoder,
        cipher=cipher,
        compressor=compressor,
    )

    stored_event2 = mapper.from_domain_event(domain_event1)
    assert mapper.to_domain_event(stored_event2) == domain_event1

    assert len(stored_event2.state) <= len(stored_event1.state)


The library's :class:`~eventsourcing.compressor.ZlibCompressor` class
uses Python's :mod:`zlib` module.

The mapper expects an instance of the abstract base class
:class:`~eventsourcing.compressor.Compressor`, and
:class:`~eventsourcing.compressor.ZlibCompressor` implements this
abstract base class, so if you want to use another compression
strategy simply implement the base class.


.. _Notification objects:

Notification objects
====================

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
section of a :ref:`notification log<Notification Log>`.
It will be returned when selecting event notifications from a
:ref:`recorder<Recorder>`, and presented in an application by a
:ref:`notification log<Notification log>`.

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


.. _Tracking objects:

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
        application_name="bounded_context1",
    )

.. _Recorder:

Recorder
========

A recorder adapts a database management system for the purpose of
recording stored events. It is used by an :ref:`event store <Store>`.

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

The library includes in its :mod:`~eventsourcing.sqlite` module
recorder classes for SQLite that use the Python :mod:`sqlite3`
module, and in its :mod:`~eventsourcing.postgres` module recorders for
PostgreSQL that use the third party :mod:`psycopg2` module.

Recorder classes are conveniently constructed by using an
:ref:`infrastructure factory <Factory>`. For illustrative purposes, the direct
use of the library's SQLite recorders is shown below. The other persistence
modules follow a similar naming scheme and pattern of use.

.. code:: python

    from eventsourcing.sqlite import SQLiteAggregateRecorder
    from eventsourcing.sqlite import SQLiteApplicationRecorder
    from eventsourcing.sqlite import SQLiteProcessRecorder
    from eventsourcing.sqlite import SQLiteDatastore

    datastore = SQLiteDatastore(db_name=":memory:")
    aggregate_recorder = SQLiteAggregateRecorder(datastore, "snapshots")
    aggregate_recorder.create_table()

    application_recorder = SQLiteApplicationRecorder(datastore)
    application_recorder.create_table()

    datastore = SQLiteDatastore(db_name=":memory:")
    process_recorder = SQLiteProcessRecorder(datastore)
    process_recorder.create_table()


The library also includes in the :mod:`~eventsourcing.popo` module recorders
that use "plain old Python objects", which simply keep stored events in a
data structure in memory, and provides the fastest alternative for rapid
development of event sourced applications (~4x faster than using SQLite, and
~20x faster than using PostgreSQL).

Recorders compatible with this version of the library for popular ORMs such
as SQLAlchemy and Django, specialist event stores such as EventStoreDB and
AxonDB, and NoSQL databases such as DynamoDB and MongoDB are forthcoming.


.. _Store:

Event store
===========

An event store provides a common interface for storing and retrieving
domain event objects. It combines a :ref:`mapper <Mapper>` and a
:ref:`recorder <Recorder>`, so that domain event objects can be
converted to stored event objects and then stored event objects
can be recorded in a datastore.

The library's :class:`~eventsourcing.persistence.EventStore` class must
be constructed with a :ref:`mapper <Mapper>` and a :ref:`recorder <Recorder>`.

The :class:`~eventsourcing.persistence.EventStore` has an object method
:func:`~eventsourcing.persistence.EventStore.put` which can be used to
store a list of new domain event objects. If any of these domain event
objects conflict with any already existing domain event object (because
they have the same aggregate ID and version number), an exception will
be raised and none of the new events will be stored.

The :class:`~eventsourcing.persistence.EventStore` has an object method
:func:`~eventsourcing.persistence.EventStore.get` which can be used to
get a list of domain event objects. Only the :data:`originator_id` argument
is required, which is the ID of the aggregate for which existing events
are wanted. The arguments :data:`gt`, :data:`lte`, :data:`limit`, and :data:`desc`
condition the selection of events to be greater than a particular version
number, less then or equal to a particular version number, limited in
number, or selected in a descending fashion. The selection is by default
ascending, unlimited, and otherwise unrestricted such that all the previously
stored domain event objects for a particular aggregate will be returned
in the order in which they were created.


.. code:: python

    from eventsourcing.persistence import EventStore

    event_store = EventStore(
        mapper=mapper,
        recorder=application_recorder,
    )

    event_store.put([domain_event1])

    domain_events = list(event_store.get(id1))
    assert domain_events == [domain_event1]


.. _Factory:

Infrastructure factory
======================

An infrastructure factory helps with the construction of the persistence
infrastructure objects mentioned above. By reading and responding to
particular environment variables, the persistence infrastructure of an
event-sourced application can be easily
:ref:`configured in different ways<Persistence>` at different times.

The library's :class:`~eventsourcing.persistence.InfrastructureFactory` class
is a base class for concrete infrastructure factories that help with the construction
of persistence objects that use a particular database in a particular way.

The class method :func:`~eventsourcing.persistence.InfrastructureFactory.construct`
will, by default, construct the library's "plain old Python objects"
infrastructure :class:`~eventsourcing.popo.Factory`, which uses recorders that simply
keep stored events in a data structure in memory (see :mod:`eventsourcing.popo`).

.. code:: python

    from eventsourcing.persistence import InfrastructureFactory

    factory = InfrastructureFactory.construct()

    recorder = factory.application_recorder()
    mapper = factory.mapper(transcoder=transcoder)
    event_store = factory.event_store(
        mapper=mapper,
        recorder=recorder,
    )

    event_store.put([domain_event1])
    stored_events = list(event_store.get(id1))
    assert stored_events == [domain_event1]


.. _SQLite:

SQLite
======

The module :mod:`eventsourcing.sqlite` supports storing events in SQLite.

The library's SQLite :class:`~eventsourcing.sqlite.Factory` uses environment variables
``SQLITE_DBNAME`` and ``CREATE_TABLE``.

The ``SQLITE_DBNAME`` value is the name of a database, normally a file path, but
the special name ``:memory:`` can be used to create an in-memory database.

The environment variable ``CREATE_TABLE`` may be control whether database tables are created.
If the tables already exist, the ``CREATE_TABLE`` may be set to a "false" value (``"n"``,
``"no"``, ``"f"``, ``"false"``, ``"off"``, or ``"0"``). This value is by default "true"
which is normally okay because the tables are created only if they do not exist.

.. code:: python

    import os

    os.environ["INFRASTRUCTURE_FACTORY"] = "eventsourcing.sqlite:Factory"
    os.environ["SQLITE_DBNAME"] = ":memory:"

    factory = InfrastructureFactory.construct()

    recorder = factory.application_recorder()
    mapper = factory.mapper(transcoder=transcoder)
    event_store = factory.event_store(
        mapper=mapper,
        recorder=recorder,
    )

    event_store.put([domain_event1])
    stored_events = list(event_store.get(id1))
    assert stored_events == [domain_event1]


.. _PostgresSQL:

PostgreSQL
==========

The module :mod:`eventsourcing.postgres` supports storing events in PostgresSQL.

The library's PostgreSQL :class:`~eventsourcing.sqlite.Factory` uses environment variables
``POSTGRES_DBNAME``, ``POSTGRES_HOST``, ``POSTGRES_PORT``, ``POSTGRES_USER``,
``POSTGRES_PASSWORD``, ``POSTGRES_CONN_MAX_AGE``, ``POSTGRES_PRE_PING``, and ``CREATE_TABLE``.

The environment variables ``POSTGRES_DBNAME``, ``POSTGRES_HOST``, ``POSTGRES_PORT``, ``POSTGRES_USER``, and
``POSTGRES_PASSWORD`` are used to set the name of a database, the database server's
host name, the database user name, and the password for that user.

The environment variable ``POSTGRES_CONN_MAX_AGE`` is used to control the length of time in
seconds before a connection is closed. By default this value is not set, and connections will
be reused indefinitely (or until an operational database error is encountered). If this
value is set to a positive integer, the connection will be closed after this number of
seconds from the time it was created, but only when the connection is idle. If this value
if set to zero, each connection will only be used for one transaction. Setting this value
to an empty string has the same effect as not setting this value. Setting this value to
any other value will cause an environment error exception to be raised. If your database
terminates idle connections after some time, you should set ``POSTGRES_CONN_MAX_AGE`` to a
lower value, so that attempts are not made to use connections that have been terminated
by the database server.

The environment variable ``POSTGRES_PRE_PING`` may be used to enable pessimistic disconnection
handling. Setting this to a "true" value (``"y"``, ``"yes"``, ``"t"``, ``"true"``, ``"on"``,
or ``"1"``) means database connections will be checked that they are usable before executing
statements, and database connections remade if the connection is not usable. This value is
by default "false", meaning connections will not be checked before they are reused. Enabling
this option will incur a small impact on performance.

The environment variable ``CREATE_TABLE`` may be control whether database tables are created.
If the tables already exist, the ``CREATE_TABLE`` may be set to a "false" value (``"n"``,
``"no"``, ``"f"``, ``"false"``, ``"off"``, or ``"0"``). This value is by default "true"
which is normally okay because the tables are created only if they do not exist.

.. code:: python

    import os

    os.environ["INFRASTRUCTURE_FACTORY"] = "eventsourcing.postgres:Factory"
    os.environ["POSTGRES_DBNAME"] = "eventsourcing"
    os.environ["POSTGRES_HOST"] = "127.0.0.1"
    os.environ["POSTGRES_PORT"] = "5432"
    os.environ["POSTGRES_USER"] = "eventsourcing"
    os.environ["POSTGRES_PASSWORD"] = "eventsourcing"
    os.environ["POSTGRES_CONN_MAX_AGE"] = "10"

..
    from eventsourcing.tests.test_postgres import drop_postgres_table
    factory = InfrastructureFactory.construct()
    drop_postgres_table(factory.datastore, "stored_events")


.. code:: python

    factory = InfrastructureFactory.construct()

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
