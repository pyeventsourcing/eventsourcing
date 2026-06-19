=================================================
:mod:`~eventsourcing.persistence` --- Persistence
=================================================

This module provides a :ref:`cohesive mechanism <Cohesive mechanism>`
for storing and retrieving :ref:`domain events <Domain events>`.

This module, along with the :ref:`concrete persistence modules <Persistence>` that
adapt particular database management systems, are the most important parts of this
library. The other modules (:doc:`domain </topics/domain>`, :doc:`application </topics/application>`,
:doc:`projection </topics/projection>`, and :doc:`system </topics/system>`) serve *primarily* as
guiding examples of how to use the persistence modules to build event-sourced applications and
event-driven systems.

Requirements
============

These requirements were written after industry-wide discussions about what
is and isn't event sourcing demonstrated the need for such a statement. They
effectively summarise the technical character of an adequate persistence mechanism
for event sourcing, and happen to describe what this module essentially implements.

In summary: there needs to be one sequence of events for each aggregate, and usually
one sequence for the application as a whole; the positions in these sequences must be
occupied uniquely, with new additions inserted at the end of the sequence; each event
should be recorded in both kinds of sequence atomically; and this atomic recording can
be extended to include unique records that track which event notification has been
processed when new events result from processing an event notification.

1. We need a **universal type** for storing :ref:`domain events <Domain events>`,
because an application will have different types of domain event and we
want to record all of the events in the same way. The term 'stored event'
shall be used to refer to objects of this type.

2. We need to record each domain event in **a sequence for its aggregate**,
because we also need to select the events for an :ref:`aggregate <Aggregates>`
when reconstructing an aggregate from its events. The term 'aggregate sequence'
shall be used to refer to the sequence of events of an individual aggregate.

3. We need domain events to be **recorded in sequential order**
in their aggregate sequence, because domain events will be generated
in sequential order, and used in sequential order to reconstruct the
state of the aggregate.

4. We need domain events to be **recorded uniquely** in their
aggregate sequence, so that only one domain event can be recorded
at any given position in its aggregate sequence. :ref:`Aggregate events <Aggregate events>`
and :ref:`snapshots <Snapshots>` will therefore need to be stored separately.
This requirement provides optimistic *concurrency* control,
but it also protects against any *subsequent* over-writing of recorded
domain events.

5. We sometimes need aggregate events to be positioned in
a **global sequence of event notifications** for the application
as a whole. The term 'application sequence' shall be used to refer
to the sequence of events of an application as a whole.

6. We need event notifications to be **recorded in sequential order**
in their application sequence, because we also need to propagate event
notifications in the order that they were recorded.

7. We need event notifications to be **recorded uniquely** in their
application sequence, so that only one aggregate event
can be recorded at any given position in its application
sequence. This requirement protects against any concurrent writing
or subsequent over-writing of recorded event notifications.

8. When recording an aggregate event in both an aggregate sequence and an
application sequence, we need **atomic recording of aggregate events with
event notifications**, because we need to exclude the possibility that an
aggregate event will appear in one sequence but not in the other. That is,
we need to avoid dual-writing in the recording of aggregate events and
event notifications.

9. We sometimes need to record a **notification tracking object**
that indicates both the position in an application sequence of an event
notification that has been processed, and the application to which that
sequence belongs. We need tracking records to be **recorded uniquely**.
This requirement supports knowing what has been processed and protects
against subsequent over-writing of recorded notification tracking records.

10. When tracking event notifications, we need **atomic recording of tracking
objects with new aggregate events** (or any other new application state) generated
from processing the event notification represented by that tracking object, because
we need to exclude the possibility that a tracking object will be recorded without
the consequences of processing the event notification it represents, and vice versa.
That is, we need to avoid dual writing in the consumption of event notifications.
This effectively provides "exactly once" semantics for the processing of event
notifications into recorded application state changes.

11. When recording aggregate events in an application sequence, we need the
"insert order" and the "commit order" to be the same, so that those following
an application sequence don't experience overlooking things committed later in
time that were inserted earlier in the sequence. This is a constraint on concurrent
recording of the application sequence, which effectively serialises the recording
of aggregate events in an application sequence.

12. When recording aggregate events in an application sequence, we want to
know the positions of the aggregate events in the application sequence, so that
we can detect when those aggregate events have been processed by another application
in an event-driven system.

The sections below describe how these requirements are implemented by this module.

.. _Overview:

Overview
========

A **stored event** is the universal type of object used
in the library to represent domain events of different types.
By using a common type for the representation of domain events,
all domain events can be stored and retrieved in a common way.

An **aggregate sequence** is a sequence of stored events for
an aggregate. The originator version number of the event determines
its position in its sequence.

An **event notification** is a stored event that also has a notification ID.
The notification ID identifies the position of the event in an application sequence.

An **application sequence** is a sequence of event notifications
for an application. It includes all stored events of all aggregate sequences.

A **tracking** object indicates the position of an event notification in
an application sequence.

A **recorder** inserts stored event objects in a database when domain
events are stored in an event store, and selects stored events from
a database when domain events are retrieved from an event store. Some
recorders atomically record stored events in an aggregate sequence. Some
recorders atomically record stored events in both an aggregate sequence
and an application sequence. Some recorders atomically record stored
events in both an aggregate sequence and an application sequence along
with a tracking record that indicates the position of an event notification
that was processed when those stored events were generated.

A **transcoder** serializes and deserializes the state of a domain event.

A **compressor** compresses and decompresses the serialized state of of domain event.
Compressed state may or may not also be encrypted after being compressed, or
decrypted before being decompressed.

A **cipher** encrypts and decrypts the serialized state of of domain event. The
serialized state may or may not be have been compressed before being encrypted,
or be compressed after being decrypted.

A **mapper** converts domain events to stored events, and converts
stored events back to a domain events.

An **event store** stores and retrieves domain events. The event
store uses a mapper to convert domain events to stored events, and
it uses a recorder to insert stored events in a datastore.

An **infrastructure factory** helps with the construction of persistence
infrastructure objects, providing a common interface for applications to
construct and configure a particular persistence mechanism from a particular
persistence module.


.. _Stored event objects:

Stored event
============

Stored event objects represent any type of :ref:`domain event objects <Domain events>` in
a way that allows the domain event objects to be reconstructed.

The library's :class:`~eventsourcing.persistence.StoredEvent` class
is a Python frozen data class.

.. code-block:: python

    from eventsourcing.persistence import StoredEvent

A :class:`~eventsourcing.persistence.StoredEvent` has an :class:`~eventsourcing.persistence.StoredEvent.originator_id`
attribute which is a :data:`UUID` that identifies the aggregate sequence to
which the domain event belongs. It has an :class:`~eventsourcing.persistence.StoredEvent.originator_version` attribute which
is a Python :data:`int` that identifies the position of the domain event in that
sequence.

A stored event object also has a :class:`~eventsourcing.persistence.StoredEvent.state` attribute which is a Python
:data:`bytes` object, that holds the serialized state of the domain event object. And it has a
:class:`~eventsourcing.persistence.StoredEvent.topic` attribute which is a Python
:class:`str` that identifies the class of the domain event object that is being stored (see :ref:`Topics <Topics>`).

.. code-block:: python

    from uuid import uuid4

    stored_event = StoredEvent(
        originator_id=uuid4(),
        originator_version=1,
        topic="eventsourcing.model:DomainEvent",
        state=b'{"a": 4}',
    )


.. _Transcoder:

Transcoder
==========

A transcoder serializes and deserializes the state of domain events.

The library's :class:`~eventsourcing.persistence.JSONTranscoder` class
can be constructed without any arguments.

.. code-block:: python

    from eventsourcing.persistence import Transcoder, JSONTranscoder

    transcoder = JSONTranscoder()

The :data:`transcoder` object has methods :func:`~eventsourcing.persistence.JSONTranscoder.encode`
and :func:`~eventsourcing.persistence.JSONTranscoder.decode`  which are used to perform the
serialisation and deserialisation. The serialised state is a Python :class:`bytes` object.

.. code-block:: python

    json_bytes = transcoder.encode({"a": 4})
    copy = transcoder.decode(json_bytes)
    assert copy == {"a": 4}

The library's :class:`~eventsourcing.persistence.JSONTranscoder` uses the Python
:mod:`json` module. And so, by default, only the object types supported by that
module can be encoded and decoded.

The transcoder can be extended by registering
transcodings for the other types of object used in your domain model's event objects.
A transcoding will convert other types of object to a representation of the object
that uses other types that are supported. The transcoder method
:func:`~eventsourcing.persistence.Transcoder.register` is used to register
individual transcodings with the transcoder.

.. _Transcodings:

Transcodings
============

In order to encode and decode types of object that are not supported by
the transcoder by default, custom transcodings need to be defined in code and
registered with the :ref:`transcoder<Transcoder>` using the transcoder object's
:func:`~eventsourcing.persistence.Transcoder.register` method. A transcoding
will encode an instance of a type of object into a representation of that object
that can be encoded by the transcoder, and will decode that representation into
the original type of object. This makes it possible to transcode custom value objects,
including custom types that contain custom types.

The library includes a limited collection of custom transcoding objects. For
example, the library's :class:`~eventsourcing.persistence.UUIDAsHex` class
transcodes a Python :class:`~uuid.UUID` objects as a hexadecimal string.

.. code-block:: python

    from uuid import UUID
    from eventsourcing.persistence import Transcoding, UUIDAsHex

    uuid_transcoding = UUIDAsHex()

    id1 = UUID("ffffffffffffffffffffffffffffffff")
    python_str = uuid_transcoding.encode(id1)
    copy = uuid_transcoding.decode(python_str)
    assert copy == id1


The library's :class:`~eventsourcing.persistence.DatetimeAsISO` class
transcodes Python :class:`~datetime.datetime` objects as ISO strings.

.. code-block:: python

    from datetime import datetime
    from eventsourcing.persistence import DatetimeAsISO

    datetime_transcoding = DatetimeAsISO()

    datetime1 = datetime(2021, 12, 31, 23, 59, 59)
    python_str = datetime_transcoding.encode(datetime1)
    copy = datetime_transcoding.decode(python_str)
    assert copy == datetime1


The library's :class:`~eventsourcing.persistence.DecimalAsStr` class
transcodes Python :class:`~decimal.Decimal` objects as decimal strings.

.. code-block:: python

    from decimal import Decimal
    from eventsourcing.persistence import DecimalAsStr

    decimal_transcoding = DecimalAsStr()

    decimal1 = Decimal("1.2345")
    python_str = decimal_transcoding.encode(decimal1)
    copy = decimal_transcoding.decode(python_str)
    assert copy == decimal1


Transcodings are registered with the transcoder using the transcoder object's
:func:`~eventsourcing.persistence.Transcoder.register` method.

.. code-block:: python

    transcoder.register(UUIDAsHex())
    transcoder.register(DatetimeAsISO())
    transcoder.register(DecimalAsStr())

    json_bytes = transcoder.encode(id1)
    copy = transcoder.decode(json_bytes)
    assert copy == id1

    json_bytes = transcoder.encode(datetime1)
    copy = transcoder.decode(json_bytes)
    assert copy == datetime1

    json_bytes = transcoder.encode(decimal1)
    copy = transcoder.decode(json_bytes)
    assert copy == decimal1


Attempting to serialize an unsupported type will result in a Python :class:`TypeError`.

.. code-block:: python

    from datetime import date

    date1 = date(2021, 12, 31)

    try:
        JSONTranscoder().encode(date1)
    except TypeError as e:
        assert e.args[0] == (
            "Object of type <class 'datetime.date'> is not serializable. "
            "Please define and register a custom transcoding for this type."
        )
    else:
        raise AssertionError("TypeError not raised")


Attempting to deserialize an unsupported type will also result in a Python :class:`TypeError`.

.. code-block:: python

    try:
        JSONTranscoder().decode(json_bytes)
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

.. code-block:: python

    from eventsourcing.persistence import Transcoding

    class DateAsISO(Transcoding):
        type = date
        name = "date_iso"

        def encode(self, obj: date) -> str:
            return obj.isoformat()

        def decode(self, data: str) -> date:
            return date.fromisoformat(data)

    transcoder.register(DateAsISO())
    json_bytes = transcoder.encode(date1)
    copy = transcoder.decode(json_bytes)
    assert copy == date1


Please note, due to the way the Python :mod:`json` module works, it isn't
currently possible to transcode subclasses of the basic Python types that
are supported by default, such as :class:`dict`, :class:`list`, :class:`tuple`,
:class:`str`, :class:`int`, :class:`float`, and :class:`bool`. This behaviour
also means an encoded :class:`tuple` will be decoded as a :class:`list`.
If you don't want tuples to be converted to lists, please avoid using tuples
in event objects. This behaviour is coded in Python as C code, and can't be
suspended without avoiding the use of this C code and thereby incurring a
performance penalty in the transcoding of domain event objects.

.. code-block:: python

    json_bytes = transcoder.encode((1, 2, 3))
    copy = transcoder.decode(json_bytes)
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

.. code-block:: python

    from typing import Any
    from uuid import UUID

    class SimpleCustomValue:
        def __init__(self, id: UUID, date: date):
            self.id = id
            self.date = date

        def __eq__(self, other: object) -> bool:
            return (
                isinstance(other, SimpleCustomValue) and
                self.id == other.id and self.date == other.date
            )

    class ComplexCustomValue:
        def __init__(self, value: SimpleCustomValue):
            self.value = value

        def __eq__(self, other: object) -> bool:
            return (
                isinstance(other, ComplexCustomValue) and
                self.value == other.value
            )

    class SimpleCustomValueAsDict(Transcoding):
        type = SimpleCustomValue
        name = "simple_custom_value"

        def encode(self, obj: SimpleCustomValue) -> dict[str, Any]:
            return {"id": obj.id, "date": obj.date}

        def decode(self, data: dict[str, Any]) -> SimpleCustomValue:
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

.. code-block:: python

    transcoder.register(SimpleCustomValueAsDict())
    transcoder.register(ComplexCustomValueAsDict())

We can now transcode an instance of :class:`ComplexCustomValueAsDict`.

.. code-block:: python

    obj1 = ComplexCustomValue(
        SimpleCustomValue(
            id=UUID("b2723fe2c01a40d2875ea3aac6a09ff5"),
            date=date(2000, 2, 20)
        )
    )

    json_bytes = transcoder.encode(obj1)
    copy = transcoder.decode(json_bytes)
    assert copy == obj1


As you can see from the bytes representation below, the transcoder puts the return value
of each transcoding's :func:`encode` method in a Python :class:`dict` that has two values
:data:`_data_` and :data:`_type_`. The :data:`_data_` value is the return value of the
transcoding's :func:`encode` method, and the :data:`_type_` value is the name of the
transcoding. For this reason, it is necessary to avoid defining model objects to have a
Python :class:`dict` that has only two attributes :data:`_data_` and :data:`_type_`, and
avoid defining transcodings that return such a thing.

.. code-block:: python

    assert json_bytes == (
        b'{"_type_":"complex_custom_value","_data_":{"_type_":'
        b'"simple_custom_value","_data_":{"id":{"_type_":'
        b'"uuid_hex","_data_":"b2723fe2c01a40d2875ea3aac6a09ff5"},'
        b'"date":{"_type_":"date_iso","_data_":"2000-02-20"}'
        b'}}}'
    )


.. _Mapper:

Mapper
======

A mapper maps between domain event objects and stored event objects. It brings
together a :ref:`transcoder<Transcoder>`, and optionally a :ref:`cipher<Encryption>`
and a :ref:`compressor<Compression>`. It is used by an :ref:`event store<Store>`.

The library's :class:`~eventsourcing.persistence.DataclassMapper` class implements
the abstract base class :class:`~eventsourcing.persistence.Mapper` and
must be constructed with a :ref:`transcoder<Transcoder>` object.

.. code-block:: python

    from eventsourcing.persistence import DataclassMapper

    mapper = DataclassMapper[UUID](transcoder=transcoder)

The :class:`~eventsourcing.persistence.DataclassMapper` class defines a :func:`~eventsourcing.persistence.DataclassMapper.to_stored_event`
method, which converts :class:`~eventsourcing.domain.DomainEvent` objects to :class:`~eventsourcing.persistence.StoredEvent`
objects.

.. code-block:: python

    from eventsourcing.domain import DomainEvent

    class MyDomainEvent(DomainEvent):
        obj: ComplexCustomValue

    domain_event = MyDomainEvent(
        originator_id=id1,
        originator_version=1,
        obj=obj1,
    )

    stored_event = mapper.to_stored_event(domain_event)
    assert isinstance(stored_event, StoredEvent)


The :class:`~eventsourcing.persistence.DataclassMapper` class defines a :func:`~eventsourcing.persistence.DataclassMapper.to_domain_event`
method, which converts :class:`~eventsourcing.persistence.StoredEvent` objects to :class:`~eventsourcing.domain.DomainEvent`
objects.

.. code-block:: python

    assert mapper.to_domain_event(stored_event) == domain_event


.. _Compression:

Compression
===========

The :class:`~eventsourcing.persistence.DataclassMapper` class has an optional constructor argument, ``compressor``,
which accepts :class:`~eventsourcing.compressor.Compressor` objects. A compressor will compress and decompress
the state of stored events, and can be used to reduce the size of stored events, reducing the transport time
between an application and its database, and reducing the size of the database files.

The library's :class:`~eventsourcing.compressor.ZlibCompressor` class
implements the abstract base class :class:`~eventsourcing.compressor.Compressor`.
It can be used to compress and decompress the state of stored events using
Python's :mod:`zlib` module.

.. code-block:: python

    from eventsourcing.compressor import ZlibCompressor

    compressor = ZlibCompressor()

    mapper = DataclassMapper(
        transcoder=transcoder,
        compressor=compressor,
    )

    compressed_stored_event = mapper.to_stored_event(domain_event)
    assert mapper.to_domain_event(compressed_stored_event) == domain_event

The compressed state of a stored event will normally be much
smaller than the state of a stored event that is not compressed.

.. code-block:: python

    assert len(compressed_stored_event.state) < len(stored_event.state)

If you want to use another compression strategy, then implement the
:class:`~eventsourcing.compressor.Compressor` base class.


.. _Encryption:

Encryption
==========

The :class:`~eventsourcing.persistence.DataclassMapper` class has an optional constructor argument, ``cipher``,
which accepts :class:`~eventsourcing.persistence.Cipher` objects. A cipher will encrypt and decrypt the state
of stored events within an event-sourced application, inhibiting disclosure of sensitive information in
case of unauthorised access to an application's database files and backups, or network interception.

The library's :class:`eventsourcing.cipher.AESCipher` class
implements the abstract base class :class:`~eventsourcing.persistence.Cipher`.
It can be used to cryptographically encode and decode the state of stored
events using the `AES cipher <https://pycryptodome.readthedocs.io/en/stable/src/cipher/aes.html>`_
from the `PyCryptodome library <https://pycryptodome.readthedocs.io/en/stable/index.html>`_
in `GCM mode <https://pycryptodome.readthedocs.io/en/stable/src/cipher/modern.html#gcm-mode>`_.
AES is a very fast and secure symmetric block cipher, and is the de facto
standard for symmetric encryption. Galois/Counter Mode (GCM) is a mode of
operation for symmetric block ciphers that is designed to provide both data
authenticity and confidentiality, and is widely adopted for its performance.

Alternatively, the library's :class:`eventsourcing.cryptography.AESCipher` class
also implements the abstract base class :class:`~eventsourcing.persistence.Cipher` and
is functionally equivalent, but uses the `Python cryptography library <https://cryptography.io>`_,
and should work as a drop-in replacement for :class:`eventsourcing.cipher.AESCipher`.

A :class:`~eventsourcing.persistence.Cipher` is constructed with an
:class:`~eventsourcing.utils.Environment` object so that that
encryption can be configured using environment variables.

The :class:`~eventsourcing.cipher.AESCipher` reads a cipher key
from environment variable ``CIPHER_KEY``. The static method
:func:`~eventsourcing.cipher.AESCipher.create_key` can be used to
generate a cipher key. The AES cipher key must be either 16, 24, or
32 bytes long. Please note, the same cipher key must be used to
decrypt stored events as that which was used to encrypt stored events.

.. code-block:: python

    from eventsourcing.cipher import AESCipher
    from eventsourcing.utils import Environment

    key = AESCipher.create_key(num_bytes=32)  # 16, 24, or 32
    environment = Environment()
    environment["CIPHER_KEY"] = key
    cipher = AESCipher(environment)

    mapper = DataclassMapper(
        transcoder=transcoder,
        cipher=cipher,
    )

    encrypted_stored_event = mapper.to_stored_event(domain_event)

    assert mapper.to_domain_event(encrypted_stored_event) == domain_event


The state of an encrypted stored event will normally be slightly larger
than the state of a stored event that is not encrypted.

.. code-block:: python

    assert len(encrypted_stored_event.state) > len(stored_event.state)

If you want to use a different cipher strategy, then implement the base
class :class:`~eventsourcing.persistence.Cipher`.


Compression and encryption
==========================

Stored events can be both compressed and encrypted.

.. code-block:: python

    mapper = DataclassMapper(
        transcoder=transcoder,
        cipher=cipher,
        compressor=compressor,
    )

    compressed_and_encrypted = mapper.to_stored_event(domain_event)
    assert mapper.to_domain_event(compressed_and_encrypted) == domain_event


The state of a stored event that is both compressed and encrypted will
usually be significantly smaller than the state of a stored event that
is neither compressed not encrypted. But it will normally be marginally
larger than the state of a stored event that is compressed but not encrypted.

.. code-block:: python

    assert len(compressed_and_encrypted.state) < len(stored_event.state)

    assert len(compressed_and_encrypted.state) > len(compressed_stored_event.state)

.. _Notification objects:

Notification
============

Event notifications are used to propagate the state of an event-sourced application in a reliable way.
A stored event can be positioned in a "total order", by attributing to each stored event a notification
ID that is higher than any that has been previously recorded. An event notification object brings together
the attributes of a stored event with its notification ID.

The library's :class:`~eventsourcing.persistence.Notification` class
is a Python frozen data class. It is a subclass of :class:`~eventsourcing.persistence.StoredEvent`.

.. code-block:: python

    from eventsourcing.persistence import Notification

    assert issubclass(Notification, StoredEvent)


The :class:`~eventsourcing.persistence.Notification` class extends :class:`~eventsourcing.persistence.StoredEvent`
with an :py:attr:`~eventsourcing.persistence.Notification.id` attribute which is a Python :data:`int` that represents
the position of a stored event in an application sequence.

.. code-block:: python

    notification = Notification(
        id=123,
        originator_id=uuid4(),
        originator_version=1,
        state=b"{}",
        topic="eventsourcing.model:DomainEvent",
    )

This class is used when selecting from and subscribing to an application sequence
with a :ref:`recorder<Recorder>`. Event notifications from application sequences
are also presented by an :doc:`application </topics/application>` in its :ref:`notification log<Notification log>`.

By recording aggregate events atomically with notification IDs,
there will never be an aggregate event that is not available to be
passed as an event notification message across a network, and there
will never be an event notification message passed across a network
that doesn't correspond to a recorded aggregate event. This solves
the problem of "dual writing" in the production of event notifications
that occurs when a domain model is updated and then separately a message
is put on a message queue, a problem of reliability that may cause
catastrophic inconsistencies in the state of a system.


.. _Tracking objects:

Tracking
========

A tracking object identifies the position of an event in an application sequence.
This is useful when the results of processing an event are to be stored by
an event processing component, so that we can ensure each event is processed
only once, and so that we can resume processing events from the correct position.

The library's :class:`~eventsourcing.persistence.Tracking` class
is a Python frozen data class.

.. code-block:: python

    from eventsourcing.persistence import Tracking

The :class:`~eventsourcing.persistence.Tracking` class has a ``notification_id``
attribute which in a Python :data:`int` that indicates the position in an application
sequence of an event notification that has been processed. And it has an
``application_name`` attribute which is a Python :class:`str` that identifies
the name of that application.

.. code-block:: python

    tracking = Tracking(
        notification_id=123,
        application_name="bounded_context1",
    )

By recording, with uniqueness constraints, a tracking object that represents the position
of an event notification in its application sequence atomically with new state that results
from processing that event notification, we can ensure that domain events are processed "at most once".
And, by resuming event processing from the position indicated by the last recorded tracking object, we
can ensure that domain events are processed "at most once". This constructs "exactly once" semantics,
and solves the problem of "dual writing" in the consumption of event notifications
that occurs when an event notification is consumed from a message queue with
updates made to materialised view and then separately an acknowledgement is
sent back to the message queue, a problem of reliability that may cause
catastrophic inconsistencies in the state of a system.



.. _Recorder:

Recorders
=========

A recorder object adapts a database management system for the purposes of event sourcing.

This library defines four kinds of recorder.

An **aggregate recorder** simply stores domain events in aggregate sequences,
without also positioning the stored events in a total order. An aggregate
recorder can be used for storing snapshots of aggregates in an application,
and also for storing aggregate events in an application that will not provide
event notifications.

An **application recorder** extends an aggregate recorder
by also positioning stored events in an application sequence.
Application recorders can be used for storing aggregate events
in applications that will provide event notifications.

An **tracking recorder** supports the atomic recording of a tracking
object along with new state. The tracking object indicates the position
in an application sequence of an event notification that was being processed
when the new state was generated.

A **process recorder** combines the method of an application recorder and a
tracking recorder so that stored events can be recorded atomically with a
tracking object.

The library has an abstract base class for each kind of recorder. These abstract base classes
are implemented in concrete "persistence modules" that each encapsulate a particular database
management system (DBMS) or object-relational mapper (ORM). This library includes a persistence
module that keeps events in memory using :ref:`"plain old Python objects" <popo-module>`, which
is very fast and useful for development but it isn't suitable for production because events are not
written to disk. This library also includes a :ref:`persistence module for SQLite <sqlite-module>`
and a :ref:`persistence module for PostgreSQL <postgres-module>`.
:ref:`Other persistence modules <other-persistence-modules>` are available.

Recorder classes are conveniently constructed by using an
:ref:`infrastructure factory <Factory>`.


.. _Aggregate recorder:

Aggregate recorder
------------------

The library's :class:`~eventsourcing.persistence.AggregateRecorder` class
is an abstract base class for recording events in aggregate sequences.
The methods :func:`~eventsourcing.persistence.AggregateRecorder.insert_events`
and :func:`~eventsourcing.persistence.AggregateRecorder.select_events` define method
signatures for inserting and selecting :ref:`stored event objects <Stored event objects>`.

.. literalinclude:: ../../eventsourcing/persistence.py
   :pyobject: AggregateRecorder


.. _Application recorder:

Application recorder
--------------------

The library's :class:`~eventsourcing.persistence.ApplicationRecorder` class is an abstract base class
for recording :ref:`stored event objects <Stored event objects>` in both aggregate and application sequences.
:class:`~eventsourcing.persistence.ApplicationRecorder` is a subclass of
the :ref:`aggregate recorder <Aggregate recorder>` class.

The :func:`~eventsourcing.persistence.ApplicationRecorder.select_notifications` method
defines a method signature for selecting :ref:`notification objects <Notification objects>`
from an application sequence.

The :func:`~eventsourcing.persistence.ApplicationRecorder.max_notification_id` method
defines a method signature for discovering last notification ID of the application
sequence, for example when estimating progress when processing the event notifications
of an application.

The :func:`~eventsourcing.persistence.ApplicationRecorder.subscribe` method
defines a method signature for "subscribing" to the application sequence. This
allows iterating over already recorded events, and then also events recorded
after the subscription has begun.

.. literalinclude:: ../../eventsourcing/persistence.py
   :pyobject: ApplicationRecorder

.. _Tracking recorder:

Tracking recorder
-----------------

The library's :class:`~eventsourcing.persistence.TrackingRecorder` class is an abstract base class
for recording :ref:`tracking objects <Tracking objects>` and querying successfully recorded tracking
objects.

The :func:`~eventsourcing.persistence.TrackingRecorder.insert_tracking` method defines a method signature for
recording tracking objects.

The :func:`~eventsourcing.persistence.TrackingRecorder.max_tracking_id` method defines a method signature for
discovering the notification ID of the last successfully recorded tracking object. This is useful when resuming
the processing of event notifications from an application sequence.

The :func:`~eventsourcing.persistence.TrackingRecorder.has_tracking_id` method defines a method signature for
discovering whether an event notification has been successfully processed, and can be used by user interfaces
to poll for an eventually-consistent materialised view of the state of an event-sourced application to be updated.

The :func:`~eventsourcing.persistence.TrackingRecorder.wait` method defines a method for waiting until a tracking
object has been recorded, and can be used by user interfaces to wait for an eventually-consistent materialised
view of the state of an event-sourced application to be updated. It calls
:func:`~eventsourcing.persistence.TrackingRecorder.has_tracking_id` with exponential backoff until
the given timeout (seconds), optionally interrupted by the setting of a given event.

.. literalinclude:: ../../eventsourcing/persistence.py
   :pyobject: TrackingRecorder

.. _Process recorder:

Process recorder
----------------

The library's :class:`~eventsourcing.persistence.ProcessRecorder` class is an abstract base class
for recording :ref:`stored event objects <Stored event objects>` in both an aggregate and application sequences,
along with :ref:`tracking objects <Tracking objects>`. :class:`~eventsourcing.persistence.ProcessRecorder` is a
subclass of the :ref:`application recorder <Application recorder>` and :ref:`tracking recorder <Tracking recorder>`
classes.

Concrete process recorders will extend the :func:`~eventsourcing.persistence.AggregateRecorder.insert_events`
method so that a :ref:`tracking object <Tracking objects>` will be recorded within the same transaction
as the events.

.. literalinclude:: ../../eventsourcing/persistence.py
   :pyobject: ProcessRecorder


Persistence modules
===================

Persistence modules encapsulate a particular database management system (DBMS) or
object-relational mapper (ORM), by implementing :ref:`recorder classes<Recorder>`.

.. _popo-module:

POPO module
-----------

The :mod:`eventsourcing.popo` persistence module has recorders
that use "plain old Python objects" to keep stored events in a
data structure in memory. These recorders provide the fastest
way of running an application, and thereby support rapid development
of event-sourced applications. Stored events can be recorded
and retrieved in microseconds, allowing a test suite to run in milliseconds.

The :class:`~eventsourcing.popo.POPOAggregateRecorder` class implements the
:ref:`aggregate recorder <Aggregate recorder>` abstract base class.

.. code-block:: python

    from eventsourcing.popo import POPOAggregateRecorder

    # Construct aggregate recorder.
    aggregate_recorder = POPOAggregateRecorder()

    # Insert stored events.
    aggregate_recorder.insert_events([stored_event])

    # Select stored events from an aggregate sequence.
    recorded_events = aggregate_recorder.select_events(stored_event.originator_id)
    assert recorded_events[0] == stored_event


The :class:`~eventsourcing.popo.POPOApplicationRecorder` class
implements the :ref:`application recorder <Application recorder>` abstract base class
by extending :class:`~eventsourcing.popo.POPOAggregateRecorder`.

.. code-block:: python

    from eventsourcing.popo import POPOApplicationRecorder

    # Construct application recorder.
    application_recorder = POPOApplicationRecorder()

    # Insert stored events.
    application_recorder.insert_events([stored_event])

    # Select stored events from an aggregate sequence.
    recorded_events = application_recorder.select_events(stored_event.originator_id)
    assert recorded_events[0] == stored_event

    # Select notifications from the application sequence.
    notifications = application_recorder.select_notifications(start=1, limit=10)
    assert notifications[0].id == 1
    assert notifications[0].originator_id == stored_event.originator_id
    assert notifications[0].originator_version == stored_event.originator_version
    assert notifications[0].state == stored_event.state
    assert notifications[0].topic == stored_event.topic

    # Subscribe to application sequence from a tracked position.
    max_tracking_id = None
    with application_recorder.subscribe(gt=max_tracking_id) as subscription:
        for notification in subscription:
            max_tracking_id = notification.id

            assert notifications[0].id == 1
            assert notifications[0].originator_id == stored_event.originator_id
            assert notifications[0].originator_version == stored_event.originator_version
            assert notifications[0].state == stored_event.state
            assert notifications[0].topic == stored_event.topic
            subscription.stop()


The :class:`~eventsourcing.popo.POPOProcessRecorder` class
implements the :ref:`process recorder <Process recorder>` abstract base class
by extending :class:`~eventsourcing.popo.POPOApplicationRecorder`.

.. code-block:: python

    from eventsourcing.popo import POPOProcessRecorder

    # Construct process recorder.
    process_recorder = POPOProcessRecorder()

    # Define a tracking object.
    tracking = Tracking(notification_id=21, application_name="upstream")

    # Insert stored events atomically with a tracking object.
    process_recorder.insert_events([stored_event], tracking=tracking)

    # Select stored events from an aggregate sequence.
    recorded_events = process_recorder.select_events(stored_event.originator_id)
    assert recorded_events[0] == stored_event

    # Select notifications from the application sequence.
    notifications = process_recorder.select_notifications(start=1, limit=10)
    assert notifications[0].id == 1
    assert notifications[0].originator_id == stored_event.originator_id
    assert notifications[0].originator_version == stored_event.originator_version
    assert notifications[0].state == stored_event.state
    assert notifications[0].topic == stored_event.topic

    # Get latest tracked position.
    assert process_recorder.max_tracking_id("upstream") == 21


.. _sqlite-module:

SQLite module
-------------

The :mod:`eventsourcing.sqlite` persistence module supports recording events in
`SQLite <https://www.sqlite.org/>`_. Recorder classes use the Python :mod:`sqlite3`
module.

The :class:`~eventsourcing.sqlite.SQLiteDatastore` class encapsulates a SQLite database
and provides a connection pool.

.. code-block:: python

    from eventsourcing.sqlite import SQLiteDatastore

    # Create an SQLite database.
    datastore = SQLiteDatastore(db_name=":memory:")

The :class:`~eventsourcing.sqlite.SQLiteAggregateRecorder` class implements
the :ref:`aggregate recorder <Aggregate recorder>` abstract base class, and provides a method
to create a database table for stored events.

.. code-block:: python

    from eventsourcing.sqlite import SQLiteAggregateRecorder

    # Create an SQLite database.
    datastore = SQLiteDatastore(db_name=":memory:")

    # Construct aggregate recorder and create database table.
    aggregate_recorder = SQLiteAggregateRecorder(datastore)
    aggregate_recorder.create_table()

    # Insert stored events.
    aggregate_recorder.insert_events([stored_event])

    # Select stored events from an aggregate sequence.
    recorded_events = aggregate_recorder.select_events(stored_event.originator_id)


The :class:`~eventsourcing.sqlite.SQLiteApplicationRecorder` class
implements the :ref:`application recorder <Application recorder>` abstract base class
by extending :class:`~eventsourcing.popo.SQLiteAggregateRecorder`.

Please note, the :class:`~eventsourcing.sqlite.SQLiteApplicationRecorder` class
does not implement the :func:`ApplicationRecorder.subscribe() <eventsourcing.persistence.ApplicationRecorder.subscribe>`
method, and so does not support subscribing to application sequences.


.. code-block:: python

    from eventsourcing.sqlite import SQLiteApplicationRecorder

    # Create an SQLite database.
    datastore = SQLiteDatastore(db_name=":memory:")

    # Construct application recorder and create database table.
    application_recorder = SQLiteApplicationRecorder(datastore)
    application_recorder.create_table()

    # Insert stored events.
    application_recorder.insert_events([stored_event])

    # Select stored events from an aggregate sequence.
    recorded_events = application_recorder.select_events(stored_event.originator_id)

    # Select notifications from the application sequence.
    notifications = application_recorder.select_notifications(start=1, limit=10)

The :class:`~eventsourcing.postgres.SQLiteTrackingRecorder` class implements the
:ref:`tracking recorder <Tracking recorder>` abstract base class, and provides
a method to create a database table for tracking records.

.. code-block:: python

    from eventsourcing.sqlite import SQLiteTrackingRecorder

    # Construct tracking recorder and create table.
    tracking_recorder = SQLiteTrackingRecorder(datastore)
    tracking_recorder.create_table()

    # Construct tracking object.
    tracking = Tracking(notification_id=21, application_name="upstream")

    # Insert tracking object.
    tracking_recorder.insert_tracking(tracking=tracking)

    # Get latest tracked position.
    assert tracking_recorder.max_tracking_id("upstream") == 21

    # Check if an event notification has been processed.
    assert tracking_recorder.has_tracking_id("upstream", 21)
    assert not tracking_recorder.has_tracking_id("upstream", 22)

The :class:`~eventsourcing.sqlite.SQLiteProcessRecorder` class
implements the :ref:`process recorder <Process recorder>` abstract base class
by extending :class:`~eventsourcing.sqlite.SQLiteApplicationRecorder`.

.. code-block:: python

    from eventsourcing.sqlite import SQLiteProcessRecorder

    # Create an SQLite database.
    datastore = SQLiteDatastore(db_name=":memory:")

    # Construct process recorder and create database table.
    process_recorder = SQLiteProcessRecorder(datastore)
    process_recorder.create_table()

    # Construct a tracking object.
    tracking = Tracking(notification_id=21, application_name="upstream")

    # Insert stored events atomically with a tracking object.
    process_recorder.insert_events([stored_event], tracking=tracking)

    # Select stored events from an aggregate sequence.
    recorded_events = process_recorder.select_events(stored_event.originator_id)

    # Select notifications from the application sequence.
    notifications = process_recorder.select_notifications(start=1, limit=10)

    # Get latest tracked position.
    assert process_recorder.max_tracking_id("upstream") == 21


.. _postgres-module:

PostgreSQL module
-----------------

The :mod:`eventsourcing.postgres` persistence module supports storing events in
`PostgreSQL <https://www.postgresql.org/>`_ using the third party `Psycopg v3 <https://www.psycopg.org>`_
package. This code is tested with PostgreSQL versions 12, 13, 14, 15, 16, and 17.

The :class:`~eventsourcing.postgres.PostgresDatastore` class encapsulates a Postgres database
and provides a connection pool.

.. code-block:: python

    from eventsourcing.postgres import PostgresDatastore

    # Construct datastore object.
    datastore = PostgresDatastore(
        dbname = "eventsourcing",
        host = "127.0.0.1",
        port = "5432",
        user = "eventsourcing",
        password = "eventsourcing",
    )

The :class:`~eventsourcing.postgres.PostgresAggregateRecorder` class implements
the :ref:`aggregate recorder <Aggregate recorder>` abstract base class, and provides
a method to create a database table for stored events.

..
    #include-when-testing
..
    from eventsourcing.tests.postgres_utils import drop_tables
    drop_tables()

.. code-block:: python

    from eventsourcing.postgres import PostgresAggregateRecorder

    # Construct aggregate recorder and create table.
    aggregate_recorder = PostgresAggregateRecorder(datastore)
    aggregate_recorder.create_table()

    # Insert stored events.
    aggregate_recorder.insert_events([stored_event])

    # Select stored events from an aggregate sequence.
    recorded_events = aggregate_recorder.select_events(stored_event.originator_id)
    assert recorded_events[0].originator_id == stored_event.originator_id



The :class:`~eventsourcing.postgres.PostgresApplicationRecorder` class
implements the :ref:`application recorder <Application recorder>`
by extending :class:`~eventsourcing.postgres.PostgresAggregateRecorder`.

..
    #include-when-testing
..
    datastore = PostgresDatastore(
        dbname = "eventsourcing",
        host = "127.0.0.1",
        port = "5432",
        user = "eventsourcing",
        password = "eventsourcing",
    )
    drop_tables()


.. code-block:: python

    from eventsourcing.postgres import PostgresApplicationRecorder

    # Construct application recorder and create table.
    application_recorder = PostgresApplicationRecorder(datastore)
    application_recorder.create_table()

    # Insert stored events.
    application_recorder.insert_events([stored_event])

    # Select stored events from an aggregate sequence.
    recorded_events = application_recorder.select_events(stored_event.originator_id)
    assert recorded_events[0].originator_id == stored_event.originator_id
    assert recorded_events[0].originator_version == stored_event.originator_version

    # Select notifications from the application sequence.
    notifications = application_recorder.select_notifications(start=1, limit=10)
    assert notifications[0].id == 1
    assert notifications[0].originator_id == stored_event.originator_id
    assert notifications[0].originator_version == stored_event.originator_version

    # Subscribe to application sequence from a tracked position.
    max_tracking_id = None
    with application_recorder.subscribe(gt=max_tracking_id) as subscription:
        for notification in subscription:
            max_tracking_id = notification.id

            assert notifications[0].id == 1
            assert notifications[0].originator_id == stored_event.originator_id
            assert notifications[0].originator_version == stored_event.originator_version
            subscription.stop()


The :class:`~eventsourcing.postgres.PostgresTrackingRecorder` class implements the
:ref:`tracking recorder <Tracking recorder>` abstract base class, and provides
a method to create a database table for tracking records.


.. code-block:: python

    from eventsourcing.postgres import PostgresTrackingRecorder

    # Construct tracking recorder and create table.
    tracking_recorder = PostgresTrackingRecorder(datastore)
    tracking_recorder.create_table()

    # Construct tracking object.
    tracking = Tracking(notification_id=21, application_name="upstream")

    # Insert tracking object.
    tracking_recorder.insert_tracking(tracking=tracking)

    # Get latest tracked position.
    assert tracking_recorder.max_tracking_id("upstream") == 21

    # Check if an event notification has been processed.
    assert tracking_recorder.has_tracking_id("upstream", 21)
    assert not tracking_recorder.has_tracking_id("upstream", 22)


The :class:`~eventsourcing.postgres.PostgresProcessRecorder` class
implements the :ref:`process recorder <Process recorder>` abstract base class
by combining and extending :class:`~eventsourcing.postgres.PostgresApplicationRecorder` and
:class:`~eventsourcing.postgres.PostgresTrackingRecorder`.

..
    #include-when-testing
..
    drop_tables()
    datastore.psycopg_type_adapters.clear()
    datastore.psycopg_python_types.clear()



.. code-block:: python

    from eventsourcing.postgres import PostgresProcessRecorder

    # Construct process recorder and create table.
    process_recorder = PostgresProcessRecorder(datastore)
    process_recorder.create_table()

    # Construct tracking object.
    tracking = Tracking(notification_id=21, application_name="upstream")

    # Insert stored events atomically with tracking object.
    process_recorder.insert_events([stored_event], tracking=tracking)

    # Select stored events from an aggregate sequence.
    recorded_events = process_recorder.select_events(stored_event.originator_id)
    assert recorded_events[0].originator_id == stored_event.originator_id

    # Select notifications from the application sequence.
    notifications = process_recorder.select_notifications(start=1, limit=10)
    assert notifications[0].id == 1
    assert notifications[0].originator_id == stored_event.originator_id
    assert notifications[0].originator_version == stored_event.originator_version

    # Get latest tracked position.
    assert process_recorder.max_tracking_id("upstream") == 21


.. _other-persistence-modules:

Other persistence modules
-------------------------

Other persistence modules are available or under development. There are
`extension projects <https://github.com/pyeventsourcing>`_
that support using popular ORMs for persistence such as
`Django <https://github.com/pyeventsourcing/eventsourcing-django#readme>`_
and `SQLAlchemy <https://github.com/pyeventsourcing/eventsourcing-sqlalchemy#readme>`_,
specialist event stores such as
`Axon Server <https://github.com/pyeventsourcing/eventsourcing-axonserver#readme>`_
and `KurrentDB <https://github.com/pyeventsourcing/eventsourcing-kurrentdb#readme>`_,
and popular NoSQL databases such as
`DynamoDB <https://github.com/pyeventsourcing/eventsourcing-dynamodb#readme>`_.


.. _Store:

Event store
===========

The library's :class:`~eventsourcing.persistence.EventStore` class provides methods for storing
and retrieving :ref:`domain event <Domain events>` objects. It combines a :ref:`mapper <Mapper>`
and a :ref:`recorder <Recorder>`, so that domain event objects will be converted to stored event
objects before being recorded, and stored events will be converted to domain event objects after
being selected.

The :class:`~eventsourcing.persistence.EventStore` class must be constructed with a :ref:`mapper <Mapper>`
and a :ref:`recorder <Recorder>`.

The :class:`~eventsourcing.persistence.EventStore` defines an object method
:func:`~eventsourcing.persistence.EventStore.put` which can be used to
store a list of new domain event objects. If any of these domain event
objects conflict with any already existing domain event object (because
they have the same aggregate ID and version number), an exception will
be raised and none of the new events will be stored.

The :class:`~eventsourcing.persistence.EventStore` class defines an object method
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

.. code-block:: python

    from eventsourcing.persistence import EventStore

    application_recorder = POPOApplicationRecorder()

    event_store = EventStore[UUID](
        mapper=mapper,
        recorder=application_recorder,
    )

    event_store.put([domain_event])

    domain_events = list(event_store.get(id1))
    assert domain_events == [domain_event]


.. _Factory:

Infrastructure factory
======================

To help with the construction of the persistence infrastructure objects
mentioned above, and to support configuring applications with environment
variables, the library provides an "infrastructure factory".

The library's :class:`~eventsourcing.persistence.InfrastructureFactory` class
is an abstract base class for infrastructure factories, which provides a
standard way for applications to select, configure, and construct recorder
classes from persistence modules. Each persistence module has a concrete
infrastructure factory.

.. code-block:: python

    from eventsourcing.persistence import InfrastructureFactory


The class method :func:`~eventsourcing.persistence.InfrastructureFactory.construct`
will construct a concrete infrastructure factory from a persistence module.

By default, it will construct the infrastructure factory from the library's
:ref:`"plain old Python objects" persistence module <popo-module>`.

.. code-block:: python

    factory = InfrastructureFactory.construct()

    assert type(factory).__name__ == "POPOFactory"
    assert type(factory).__module__ == "eventsourcing.popo"


The factory method :func:`~eventsourcing.persistence.InfrastructureFactory.aggregate_recorder`
will construct an :ref:`aggregate recorder <Aggregate recorder>` from the selected persistence module.

.. code-block:: python

    recorder = factory.aggregate_recorder()

    assert isinstance(recorder, AggregateRecorder)
    assert type(recorder).__name__ == "POPOAggregateRecorder"
    assert type(recorder).__module__ == "eventsourcing.popo"

The factory method :func:`~eventsourcing.persistence.InfrastructureFactory.application_recorder`
will construct an :ref:`application recorder <Application recorder>` from the selected persistence module.

.. code-block:: python

    recorder = factory.application_recorder()

    assert isinstance(recorder, ApplicationRecorder)
    assert type(recorder).__name__ == "POPOApplicationRecorder"
    assert type(recorder).__module__ == "eventsourcing.popo"

The factory method :func:`~eventsourcing.persistence.InfrastructureFactory.tracking_recorder`
will construct a :ref:`tracking recorder <Tracking recorder>` from the selected persistence module.

.. code-block:: python

    recorder = factory.tracking_recorder()

    assert isinstance(recorder, TrackingRecorder)
    assert type(recorder).__name__ == "POPOTrackingRecorder"
    assert type(recorder).__module__ == "eventsourcing.popo"

The factory method :func:`~eventsourcing.persistence.InfrastructureFactory.process_recorder`
will construct a :ref:`process recorder <Process recorder>` from the selected persistence module.

.. code-block:: python

    recorder = factory.process_recorder()

    assert isinstance(recorder, ProcessRecorder)
    assert type(recorder).__name__ == "POPOProcessRecorder"
    assert type(recorder).__module__ == "eventsourcing.popo"

The factory method :func:`~eventsourcing.persistence.InfrastructureFactory.transcoder`
will construct a transcoder object.

.. code-block:: python

    transcoder = factory.transcoder()
    transcoder.register(UUIDAsHex())
    transcoder.register(DatetimeAsISO())
    transcoder.register(DateAsISO())
    transcoder.register(ComplexCustomValueAsDict())
    transcoder.register(SimpleCustomValueAsDict())

The factory method :func:`~eventsourcing.persistence.InfrastructureFactory.mapper`
will construct a :ref:`mapper object <Mapper>`.

.. code-block:: python

    mapper = factory.mapper(transcoder=transcoder)

The factory method :func:`~eventsourcing.persistence.InfrastructureFactory.event_store`
will construct an :ref:`event store object <Store>`.

.. code-block:: python


    event_store = factory.event_store(
        mapper=mapper,
        recorder=recorder,
    )

    event_store.put([domain_event])
    domain_events = list(event_store.get(id1))

    assert domain_events == [domain_event]

.. _environment-variables:

Environment variables
---------------------

Environment variables can be used to select and configure persistence infrastructure.
In this way, an event-sourced application can be defined independently of any particular
persistence infrastructure, and then :ref:`easily configured <Persistence>` in different
ways at different times.

You can set the environment variable ``PERSISTENCE_MODULE`` to the :ref:`topic <Topics>` of a
persistence module before calling :func:`~eventsourcing.persistence.InfrastructureFactory.construct`.
This will condition the :func:`~eventsourcing.persistence.InfrastructureFactory.construct` method to
construct a factory from the specified persistence module.

For example, to explicitly select the :mod:`eventsourcing.popo` persistence module,
use the module name string ``'eventsourcing.popo'`` as the value of ``PERSISTENCE_MODULE``.

.. code-block:: python

    environ = Environment()
    environ["PERSISTENCE_MODULE"] = "eventsourcing.popo"
    factory = InfrastructureFactory.construct(environ)

    assert type(factory).__module__ == "eventsourcing.popo"


The environment variables ``COMPRESSOR_TOPIC``, ``CIPHER_TOPIC``, and ``CIPHER_KEY`` may be
used to enable compression and encryption of stored events.

The environment variables ``MAPPER_TOPIC`` and ``TRANSCODER_TOPIC`` can be used to
select alternative mappers and transcoders.

Persistence modules use their own particular set of environment variables, of which
some are required and some are optional.

.. _Environment object:

Environment object
------------------

The :class:`~eventsourcing.utils.Environment` class is used to encapsulate a set of environment
variables. It can be constructed with an optional ``name`` argument and a mapping of key-value pairs,
for example :data:`os.environ`.

.. code-block:: python

    environ = Environment(
        name="MyApp",
        env={
           "PERSISTENCE_MODULE": "eventsourcing.popo",
        }
    )

.. _sqlite-environment:

The :class:`~eventsourcing.utils.Environment` class has a :func:`~eventsourcing.utils.Environment.get` method
which can be used to get a value for a key.

.. code-block:: python

    value = environ.get("PERSISTENCE_MODULE")

    assert value == "eventsourcing.popo"


The :func:`~eventsourcing.utils.Environment.get` method first searches for environment variables prefixed
with the uppercase name, which can be used to distinguish between environment variables defined for different
applications. It falls back onto the standard names, and returns ``None`` if no value is found.

.. code-block:: python

    import os

    os.environ["MYAPPLICATION_PERSISTENCE_MODULE"] = "eventsourcing.postgres"
    os.environ["MYPROJECTION_PERSISTENCE_MODULE"] = "eventsourcing.sqlite"

    environ = Environment(name="MyApplication", env=os.environ)
    value = environ.get("PERSISTENCE_MODULE")
    assert value == "eventsourcing.postgres"

    environ = Environment(name="MyProjection", env=os.environ)
    value = environ.get("PERSISTENCE_MODULE")
    assert value == "eventsourcing.sqlite"


SQLite environment
------------------

Similarly, the :ref:`SQLite module<sqlite-module>` can be selected and configured with environment variables.

.. code-block:: python

    environ = Environment()
    environ["PERSISTENCE_MODULE"] = "eventsourcing.sqlite"
    environ["SQLITE_DBNAME"] = ":memory:"
    environ["SQLITE_LOCK_TIMEOUT"] = "10"
    environ["SQLITE_SINGLE_ROW_TRACKING"] = "t"
    environ["CREATE_TABLE"] = "t"


The environment variable ``SQLITE_DBNAME`` is required to set the name of a database.
The value of this variable is normally a file path, but an in-memory SQLite database
can also be specified using this variable.

Writing to a file-base SQLite database is serialised with a lock. The lock timeout can
be adjusted by setting the environment variable ``SQLITE_LOCK_TIMEOUT``. Setting this
value to a positive number of seconds will cause attempts to lock the SQLite database
for writing to timeout after that duration. By default this value is 5 (seconds).
Please note, a file-based SQLite database will have its journal mode set to use
write-ahead logging (WAL), which allows reading to proceed concurrently reading
and writing.

The optional environment variable ``SQLITE_SINGLE_ROW_TRACKING`` may be used to disable the
single-row tracking implementation of tracking recorders, which uses one row in a tracking table
per application name and which is the default, and instead continue with the legacy multi-row tracking
implementation, which records a new row for each tracking object. Setting this to a "true" value
(``"y"``, ``"yes"``, ``"t"``, ``"true"``, ``"on"``, or ``"1"``) has no effect because that is the
default. Setting this value to to a "false" value (``"n"``, ``"no"``, ``"f"``, ``"false"``, ``"off"``,
or ``"0"``) will mean that tracking recorders will continue with the legacy multi-row tracking
implementation, unless a table for single-row tracking has already been created, in which case an exception
will be raised at runtime. Migration from multi-row tracking to single-row tracking will automatically happen
when a tracking recorder is constructed unless this value is "false" or ``CREATE_TABLE`` is "false".

The optional environment variable ``CREATE_TABLE`` controls whether or not database tables are
created when a recorder is constructed by a factory. If the tables already exist, the ``CREATE_TABLE``
may be set to a "false" value (``"n"``, ``"no"``, ``"f"``, ``"false"``, ``"off"``, or ``"0"``).
This value is by default "true" which is normally okay because the tables are created only if they
do not exist.

Having configured the environment to use SQLite, the infrastructure can be
constructed and used in a standard way.

.. code-block:: python

    factory = InfrastructureFactory.construct(environ)
    recorder = factory.application_recorder()
    assert isinstance(recorder, SQLiteApplicationRecorder)

    mapper = factory.mapper(transcoder=transcoder)
    event_store = factory.event_store(
        mapper=mapper,
        recorder=recorder,
    )

    event_store.put([domain_event])
    domain_events = list(event_store.get(id1))

    assert domain_events == [domain_event]

Various alternatives for specifying in-memory SQLite databases are listed below.

.. code-block:: python

    # Configure SQLite database URI. Either use a file-based DB;
    environ['SQLITE_DBNAME'] = '/path/to/your/sqlite-db'

    # or use an in-memory DB with cache not shared, only works with single thread;
    environ['SQLITE_DBNAME'] = ':memory:'

    # or use an unnamed in-memory DB with shared cache, works with multiple threads;
    environ['SQLITE_DBNAME'] = 'file::memory:?mode=memory&cache=shared'

    # or use a named in-memory DB with shared cache, to create distinct databases.
    environ['SQLITE_DBNAME'] = 'file:application1?mode=memory&cache=shared'


As above, the optional environment variables ``COMPRESSOR_TOPIC``, ``CIPHER_KEY``,
and ``CIPHER_TOPIC`` may be used to enable compression and encryption of stored
events recorded in SQLite.


.. _postgres-environment:

PostgreSQL environment
----------------------

Similarly, the :ref:`PostgreSQL module<postgres-module>` can be selected and configured with environment variables.

.. code-block:: python

    environ = Environment()
    environ["PERSISTENCE_MODULE"] = "eventsourcing.postgres"
    environ["POSTGRES_DBNAME"] = "eventsourcing"
    environ["POSTGRES_HOST"] = "127.0.0.1"
    environ["POSTGRES_PORT"] = "5432"
    environ["POSTGRES_USER"] = "eventsourcing"
    environ["POSTGRES_PASSWORD"] = "eventsourcing"
    environ["POSTGRES_CONNECT_TIMEOUT"] = "30"
    environ["POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT"] = "5"
    environ["POSTGRES_POOL_SIZE"] = "5"
    environ["POSTGRES_MAX_OVERFLOW"] = "10"
    environ["POSTGRES_MAX_WAITING"] = "0"
    environ["POSTGRES_CONN_MAX_AGE"] = ""
    environ["POSTGRES_PRE_PING"] = "n"
    environ["POSTGRES_LOCK_TIMEOUT"] = "5"
    environ["POSTGRES_SCHEMA"] = "public"
    environ["POSTGRES_SINGLE_ROW_TRACKING"] = "y"
    environ["CREATE_TABLE"] = "t"


The environment variables ``POSTGRES_DBNAME``, ``POSTGRES_HOST``, ``POSTGRES_PORT``,
``POSTGRES_USER``, and ``POSTGRES_PASSWORD`` (or ``POSTGRES_GET_PASSWORD_TOPIC``) are
required to set the name of a database, the database server's host name and port number,
and the database user name and password.

As an alternative to setting a fixed password in ``POSTGRES_PASSWORD``, you can set
``POSTGRES_GET_PASSWORD_TOPIC`` to indicate the :ref:`topic <Topics>` of a function
that returns passwords. This function will be called each time when creating new database
connections. This variable supports using database services authenticated with Identity
Access Management (IAM), sometimes referred to as token-based authentication, for which
the password is a token that is changed perhaps every 15 minutes. If ``POSTGRES_GET_PASSWORD_TOPIC``
is set, the ``POSTGRES_PASSWORD`` variable is not required and will be ignored. The value
of this variable should be resolvable using :func:`~eventsourcing.utils.resolve_topic` to
a Python function that expects no arguments and returns a Python :class:`str`.

The optional environment variable ``POSTGRES_CONNECT_TIMEOUT`` may be used to set
the maximum time in seconds that a client can wait to receive a connection from the pool.
If set, an integer value is required. The default value is 30.

The optional environment variable ``POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT`` may be used to
timeout sessions that are idle in a transaction. If a transaction cannot be ended for some reason,
perhaps because the database server cannot be reached, the transaction may remain in an idle
state and any locks will continue to be held. By timing out the session, transactions will be ended,
locks will be released, and the connection slot will be freed. A value of 0 means sessions in an idle
transaction will not timeout. Setting this value to a positive integer number of seconds will cause
sessions in an idle transaction to timeout after that duration has passed. The default value is 5.

The optional environment variable ``POSTGRES_POOL_SIZE`` is used to control the maximum number of
database connections that will be kept open in the connection pool. A value of 0 means there will
be zero connections maintained in the pool, and each access to the database will cause a new connection
to be made. If set, an integer value is required. The default value is 5. Please note, the pool will
only create a connection when there isn't one in the pool and a connection is needed, so that if your
application is single-threaded, only one connection will be created, even if the pool size is configured
to be greater than 1.

The optional environment variable ``POSTGRES_MAX_OVERFLOW`` is used to control the maximum number
of additional connections that can be opened, above the pool size. The maximum number of connections
that can be opened is the sum of ``POSTGRES_POOL_SIZE`` and ``POSTGRES_MAX_OVERFLOW``. However
connections that are returned to the pool when it is full will be immediately closed. If set, an
integer value is required. The default value is 10.

The optional environment variable ``POSTGRES_MAX_WAITING`` is used to control the maximum number
of connection requests that can be queued to the pool, after which new requests will fail.
If set, an integer is required. The default value is 0, which means there is no queue limit.

The optional environment variable ``POSTGRES_CONN_MAX_AGE`` is used to control the length of time
in seconds before a connection is closed when returned to the pool. If this value is zero, each
connection will only be used once. If your database terminates idle connections after some
time, you should set ``POSTGRES_CONN_MAX_AGE`` to a lower value, so that attempts are not made to
use connections that have been terminated by the database server, and so that your connections are
not suddenly terminated in the middle of a transaction. If set, an float is required. The default
value is 3600.0 (one hour).

The optional environment variable ``POSTGRES_PRE_PING`` may be used to enable pessimistic
disconnection handling. Setting this to a "true" value (``"y"``, ``"yes"``, ``"t"``, ``"true"``,
``"on"``, or ``"1"``) means database connections will be checked that they are usable before
executing statements, and database connections remade if the connection is not usable. This
value is by default "false", meaning connections will not be checked before they are reused.
Enabling this option will incur a small impact on performance.

The optional environment variable ``POSTGRES_LOCK_TIMEOUT`` may be used to enable a timeout
on acquiring an 'EXCLUSIVE' mode table lock when inserting stored events. To avoid interleaving
of inserts when writing events, an 'EXCLUSIVE' mode table lock is acquired when inserting events.
This avoids a potential issue where insert order and commit order are not the same.
Locking the table effectively serialises writing events. It prevents concurrent transactions
interleaving inserts, which would potentially cause notification log readers that are tailing
the application notification log to miss event notifications. Reading from the table can proceed
concurrently with other readers and writers, since selecting acquires an 'ACCESS SHARE' lock which
does not block and is not blocked by the 'EXCLUSIVE' lock. This issue of interleaving inserts
by concurrent writers is not exhibited by SQLite, which locks the entire database for writing,
effectively serializing the operations of concurrent readers. When its journal mode is set to
use write ahead logging, reading can proceed concurrently with writing. By default, this timeout
has the value of 0 seconds, which means attempts to acquire the lock will not timeout. Setting
this value to a positive integer number of seconds will cause attempt to obtain this lock to
timeout after that duration has passed. The lock will be released when the transaction ends.

The optional environment variable ``POSTGRES_SCHEMA`` may be used to configure the table names
used by the recorders to be qualified with a schema name. Setting this will create tables in
a specific PostgreSQL schema. See the
`PostgreSQL Schemas <https://www.postgresql.org/docs/current/ddl-schemas.html>`_
documentation for more information about creating and using PostgreSQL schemas safely.

The optional environment variable ``POSTGRES_SINGLE_ROW_TRACKING`` may be used to disable the
single-row tracking implementation of tracking recorders, which uses one row in a tracking table
per application name and which is the default, and instead continue with the legacy multi-row tracking
implementation, which records a new row for each tracking object. Setting this to a "true" value
(``"y"``, ``"yes"``, ``"t"``, ``"true"``, ``"on"``, or ``"1"``) has no effect because that is the
default. Setting this value to to a "false" value (``"n"``, ``"no"``, ``"f"``, ``"false"``, ``"off"``,
or ``"0"``) will mean that tracking recorders will continue with the legacy multi-row tracking
implementation, unless a table for single-row tracking has already been created, in which case an exception
will be raised at runtime. Migration from multi-row tracking to single-row tracking will automatically happen
when a tracking recorder is constructed unless this value is "false" or ``CREATE_TABLE`` is "false".

The optional environment variable ``CREATE_TABLE`` controls whether or not database tables are
created when a recorder is constructed by a factory. If the tables already exist, the ``CREATE_TABLE``
may be set to a "false" value (``"n"``, ``"no"``, ``"f"``, ``"false"``, ``"off"``, or ``"0"``).
This value is by default "true" which is normally okay because the tables are created only if they
do not exist.

Having configured the environment to use PostgreSQL, the infrastructure can be
constructed and used in a standard way.

..
    #include-when-testing
..
    drop_tables()
    datastore.psycopg_type_adapters.clear()
    datastore.psycopg_python_types.clear()




.. code-block:: python

    factory = InfrastructureFactory.construct(environ)
    recorder = factory.application_recorder()
    assert isinstance(recorder, PostgresApplicationRecorder)

    mapper = factory.mapper(transcoder=transcoder)
    event_store = factory.event_store(
        mapper=mapper,
        recorder=recorder,
    )

    event_store.put([domain_event])
    domain_events = list(event_store.get(id1))

    assert domain_events == [domain_event]

As above, the optional environment variables ``COMPRESSOR_TOPIC``, ``CIPHER_KEY``,
and ``CIPHER_TOPIC`` may be used to enable compression and encryption of stored
events recorded in PostgreSQL.


Code reference
==============

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
    :undoc-members:
    :special-members: __init__
    :private-members: _insert_tracking

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
    :undoc-members:
    :special-members: __init__
    :private-members: _insert_tracking

