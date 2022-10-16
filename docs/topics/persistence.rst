=================================================
:mod:`~eventsourcing.persistence` --- Persistence
=================================================

This module provides a :ref:`cohesive mechanism <Cohesive mechanism>`
for storing and retrieving :ref:`domain events <Domain events>`.

This module, along with the :ref:`concrete persistence modules <Persistence>` that
adapt particular database management systems, are the most important parts of this
library. The other modules (:doc:`domain </topics/domain>`, :doc:`application </topics/application>`,
:doc:`system </topics/system>`) serve *primarily* as guiding examples of how to use the
persistence modules to build event-sourced applications and event-driven systems.

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


Overview
========

A **stored event** is the universal type of object used
in the library to represent domain events of different types.
By using a common type for the representation of domain events,
all domain events can be stored and retrieved in a common way.

An **aggregate sequence** is a sequence of stored events for
an aggregate. The originator version number of the event determines
its position in its sequence.

An **event notification** is a stored event that also has an notification ID.
The notification ID identifies the position of a the event in this sequence.

An **application sequence** is a sequence of event notifications
for an application.

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

A stored event object represents a domain event in a way that allows
the domain event object to be reconstructed.

The library's :class:`~eventsourcing.persistence.StoredEvent` class
is a Python frozen data class.

.. code-block:: python

    from eventsourcing.persistence import StoredEvent

A :class:`~eventsourcing.persistence.StoredEvent` has an ``originator_id``
attribute which is a :data:`UUID` that identifies the aggregate sequence to
which the domain event belongs. It has an ``originator_version`` attribute which
is a Python :data:`int` that identifies the position of the domain event in that
sequence. A stored event object also has a ``state`` attribute which is a Python
:data:`bytes` object that is the serialized state of the :ref:`domain event
<Domain events>` object. And it has a `topic` attribute which is a Python
:data:`str` that identifies the class of the domain event (see :ref:`Topics <Topics>`).

.. code-block:: python

    from uuid import uuid4

    stored_event = StoredEvent(
        originator_id=uuid4(),
        originator_version=1,
        state="{}",
        topic="eventsourcing.model:DomainEvent",
    )


.. _Notification objects:

Notification
============

Event notifications are used to propagate the state of an event
sourced application in a reliable way. A stored event can be
positioned in a "total order" in an application sequence, by
attributing to each stored event a notification ID that is higher
than any that has been previously recorded. An event notification
object joins together the attributes of the stored event and the
notification ID.

The library's :class:`~eventsourcing.persistence.Notification` class
is a Python frozen data class. It is a subclass of :class:`~eventsourcing.persistence.StoredEvent`.

.. code-block:: python

    from eventsourcing.persistence import Notification

    assert issubclass(Notification, StoredEvent)


The :class:`~eventsourcing.persistence.Notification` class
extends :class:`~eventsourcing.persistence.StoredEvent` with
an ``id`` attribute which is a Python :data:`int` that represents
the position of a stored event in an application sequence.

.. code-block:: python

    notification = Notification(
        id=123,
        originator_id=uuid4(),
        originator_version=1,
        state="{}",
        topic="eventsourcing.model:DomainEvent",
    )

This class is used when returning the results of selecting event
notifications from a :ref:`recorder<Recorder>`. Event notifications
are presented in an application by a :ref:`notification log<Notification log>`.

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

A tracking object identifies the position of an event notification
in an application sequence.

The library's :class:`~eventsourcing.persistence.Tracking` class
is a Python frozen data class.

.. code-block:: python

    from eventsourcing.persistence import Tracking

The :class:`~eventsourcing.persistence.Tracking` class has a ``notification_id``
attribute which in a Python :data:`int` that indicates the position in an application
sequence of an event notification that has been processed. And it has an
``application_name`` attribute which is a Python :data:`str` that identifies
the name of that application.

.. code-block:: python

    tracking = Tracking(
        notification_id=123,
        application_name="bounded_context1",
    )

By recording atomically a tracking object along with new stored event objects
that result from processing the event notification represented by the tracking
object, and by ensuring the uniqueness of tracking records, we can ensure that
a domain event notification is never processed twice. And by using the tracked
position of the last event notification that has been processed, we can resume
processing event notifications from an application at the correct next position.
This constructs "exactly once" semantics when processing event notifications, by
solving the problem of "dual writing" in the consumption of event notifications
that occurs when an event notification is consumed from a message queue with
updates made to materialized view and then separately an acknowledgement is
sent back to the message queue, a problem of reliability that may cause
catastrophic inconsistencies in the state of a system.

.. _Recorder:

Recorders
=========

A recorder object adapts a database management system for the purpose of
recording stored events. This library defines three kinds of recorder.

An **aggregate recorder** simply stores domain events in aggregate sequences,
without also positioning the stored events in a total order. An aggregate
recorder can be used for storing snapshots of aggregates in an application,
and also for storing aggregate events in an application that will not provide
event notifications.

An **application recorder** extends an aggregate recorder
by also positioning stored events in an application sequence.
Application recorders can be used for storing aggregate events
in applications that will provide event notifications.

A **process recorder** extends an application recorder by
supporting the atomic recording of stored events with a tracking
object that indicates the position in an application sequence of
an event notification. The stored events recorded with a tracking
object will have been generated whilst processing that event notification.

The library has an abstract base class for each kind of recorder.

The :class:`~eventsourcing.persistence.AggregateRecorder` class
is an abstract base class for recording events in aggregate sequences.
The methods :func:`~eventsourcing.persistence.AggregateRecorder.insert_events`
and :func:`~eventsourcing.persistence.AggregateRecorder.select_events` are
used to insert and select aggregate events.

.. literalinclude:: ../../eventsourcing/persistence.py
   :pyobject: AggregateRecorder


The :class:`~eventsourcing.persistence.ApplicationRecorder` class
is an abstract base class recording events in both an aggregate and application
sequences. It extends :class:`~eventsourcing.persistence.AggregateRecorder`.
The method :func:`~eventsourcing.persistence.ApplicationRecorder.select_notifications`
is used to select event notifications from an application sequence.
The method :func:`~eventsourcing.persistence.ApplicationRecorder.max_notification_id`
can be used to discover where is the end of the application sequence, for example
for estimating progress or time to completion when processing the
event notifications of an application.

.. literalinclude:: ../../eventsourcing/persistence.py
   :pyobject: ApplicationRecorder


The :class:`~eventsourcing.persistence.ProcessRecorder` class
is an abstract base class for recording events in both an aggregate and application
sequences along with tracking records. It extends :class:`~eventsourcing.persistence.ApplicationRecorder`.
Concrete process recorders will extend the :func:`~eventsourcing.persistence.AggregateRecorder.insert_events`
method so that tracking records will be inserted within the same transaction
as the events.
The method :func:`~eventsourcing.persistence.ProcessRecorder.max_tracking_id`
can be used to discover the position of the last event notification that
was successfully processed, for example when resuming the processing of
event notifications.

.. literalinclude:: ../../eventsourcing/persistence.py
   :pyobject: ProcessRecorder

These abstract base classes are implemented in concrete persistence
modules. The :ref:`"plain old Python objects" persistence module <popo-module>`
simply holds events in memory and is very fast and useful for development,
but it isn't suitable for production because events are not written to disk.
The core library also includes a :ref:`persistence module for SQLite <sqlite-module>`
and a :ref:`persistence module for PostgreSQL <postgres-module>`.
:ref:`Other persistence modules <other-persistence-modules>` are available.


.. _popo-module:

POPO module
===========

The persistence module :mod:`eventsourcing.popo` has recorders
that use "plain old Python objects" to keep stored events in a
data structure in memory. These recorders provide the fastest
way of running an application, and thereby support rapid development
of event-sourced applications. Stored events can be recorded
and retrieved in microseconds, allowing a test suite to run in milliseconds.

The :class:`~eventsourcing.popo.POPOAggregateRecorder` class implements
:class:`~eventsourcing.persistence.AggregateRecorder`.

.. code-block:: python

    from eventsourcing.popo import POPOAggregateRecorder

    aggregate_recorder = POPOAggregateRecorder()

    aggregate_recorder.insert_events([stored_event])

    recorded_events = aggregate_recorder.select_events(stored_event.originator_id)
    assert recorded_events[0] == stored_event


The :class:`~eventsourcing.popo.POPOApplicationRecorder` class
extends :class:`~eventsourcing.popo.POPOAggregateRecorder`
and implements :class:`~eventsourcing.persistence.ApplicationRecorder`.

.. code-block:: python

    from eventsourcing.popo import POPOApplicationRecorder

    application_recorder = POPOApplicationRecorder()

    application_recorder.insert_events([stored_event])

    recorded_events = application_recorder.select_events(stored_event.originator_id)
    assert recorded_events[0] == stored_event

    notifications = application_recorder.select_notifications(start=1, limit=10)
    assert notifications[0].id == 1
    assert notifications[0].originator_id == stored_event.originator_id
    assert notifications[0].originator_version == stored_event.originator_version
    assert notifications[0].state == stored_event.state
    assert notifications[0].topic == stored_event.topic


The :class:`~eventsourcing.popo.POPOProcessRecorder` class
extends :class:`~eventsourcing.popo.POPOApplicationRecorder`
and implements :class:`~eventsourcing.persistence.ProcessRecorder`.

.. code-block:: python

    from eventsourcing.popo import POPOProcessRecorder

    process_recorder = POPOProcessRecorder()

    tracking = Tracking(notification_id=21, application_name="upstream")

    process_recorder.insert_events([stored_event], tracking=tracking)

    recorded_events = process_recorder.select_events(stored_event.originator_id)
    assert recorded_events[0] == stored_event

    notifications = process_recorder.select_notifications(start=1, limit=10)
    assert notifications[0].id == 1
    assert notifications[0].originator_id == stored_event.originator_id
    assert notifications[0].originator_version == stored_event.originator_version
    assert notifications[0].state == stored_event.state
    assert notifications[0].topic == stored_event.topic

    assert process_recorder.max_tracking_id("upstream") == 21


Recorder classes are conveniently constructed by using an
:ref:`infrastructure factory <Factory>`.


.. _Transcoder:

Transcoder
==========

A transcoder serializes and deserializes the state of domain events.

The library's :class:`~eventsourcing.persistence.JSONTranscoder` class
can be constructed without any arguments.

.. code-block:: python

    from eventsourcing.persistence import JSONTranscoder

    transcoder = JSONTranscoder()

The :data:`transcoder` object has methods :func:`~eventsourcing.persistence.JSONTranscoder.encode`
and :func:`~eventsourcing.persistence.JSONTranscoder.decode`  which are used to perform the
serialisation and deserialisation. The serialised state is a Python :class:`bytes` object.

.. code-block:: python

    data = transcoder.encode({"a": 1})
    copy = transcoder.decode(data)
    assert copy == {"a": 1}

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
    from eventsourcing.persistence import UUIDAsHex

    transcoding = UUIDAsHex()

    id1 = UUID("ffffffffffffffffffffffffffffffff")
    data = transcoding.encode(id1)
    copy = transcoding.decode(data)
    assert copy == id1


The library's :class:`~eventsourcing.persistence.DatetimeAsISO` class
transcodes Python :class:`~datetime.datetime` objects as ISO strings.

.. code-block:: python

    from datetime import datetime
    from eventsourcing.persistence import DatetimeAsISO

    transcoding = DatetimeAsISO()

    datetime1 = datetime(2021, 12, 31, 23, 59, 59)
    data = transcoding.encode(datetime1)
    copy = transcoding.decode(data)
    assert copy == datetime1


The library's :class:`~eventsourcing.persistence.DecimalAsStr` class
transcodes Python :class:`~decimal.Decimal` objects as decimal strings.

.. code-block:: python

    from decimal import Decimal
    from eventsourcing.persistence import DecimalAsStr

    transcoding = DecimalAsStr()

    decimal1 = Decimal("1.2345")
    data = transcoding.encode(decimal1)
    copy = transcoding.decode(data)
    assert copy == decimal1


Transcodings are registered with the transcoder using the transcoder object's
:func:`~eventsourcing.persistence.Transcoder.register` method.

.. code-block:: python

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

.. code-block:: python

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

.. code-block:: python

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
    data = transcoder.encode(date1)
    copy = transcoder.decode(data)
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

.. code-block:: python

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

.. code-block:: python

    expected_data = (
        b'{"_type_":"complex_custom_value","_data_":{"_type_":'
        b'"simple_custom_value","_data_":{"id":{"_type_":'
        b'"uuid_hex","_data_":"b2723fe2c01a40d2875ea3aac6a09ff5"},'
        b'"date":{"_type_":"date_iso","_data_":"2000-02-20"}'
        b'}}}'
    )
    assert data == expected_data


.. _Mapper:

Mapper
======

A mapper maps between domain event objects and stored event objects. It brings
together a :ref:`transcoder<Transcoder>`, and optionally a :ref:`cipher<Encryption>`
and a :ref:`compressor<Compression>`. It is used by an :ref:`event store<Store>`.

The library's :class:`~eventsourcing.persistence.Mapper` class
must be constructed with a :ref:`transcoder<Transcoder>` object.

.. code-block:: python

    from eventsourcing.persistence import Mapper

    mapper = Mapper(transcoder=transcoder)

The :func:`~eventsourcing.persistence.Mapper.to_stored_event` method of the
``mapper`` object converts :class:`~eventsourcing.domain.DomainEvent` objects to
:class:`~eventsourcing.persistence.StoredEvent` objects.

.. code-block:: python

    from eventsourcing.domain import DomainEvent, TZINFO

    class MyDomainEvent(DomainEvent):
        obj: ComplexCustomValue

    domain_event = MyDomainEvent(
        originator_id=id1,
        originator_version=1,
        timestamp=MyDomainEvent.create_timestamp(),
        obj=obj1,
    )

    stored_event = mapper.to_stored_event(domain_event)
    assert isinstance(stored_event, StoredEvent)


The :func:`~eventsourcing.persistence.Mapper.to_domain_event` method of the
``mapper`` object converts :class:`~eventsourcing.persistence.StoredEvent` objects to
:class:`~eventsourcing.domain.DomainEvent` objects.

.. code-block:: python

    assert mapper.to_domain_event(stored_event) == domain_event


.. _Compression:

Compression
===========

A compressor can be used to reduce the size of stored events.

The mapper's constructor argument ``compressor`` accepts
:class:`~eventsourcing.compressor.Compressor` objects.

The library's :class:`~eventsourcing.compressor.ZlibCompressor` class
implements the abstract base class :class:`~eventsourcing.compressor.Compressor`.
It can be used to compress and decompress the state of stored events using
Python's :mod:`zlib` module.

.. code-block:: python

    from eventsourcing.compressor import ZlibCompressor

    compressor = ZlibCompressor()

    mapper = Mapper(
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

A cryptographic cipher will encrypt the state of stored events.

The mapper's constructor argument ``cipher`` accepts
:class:`~eventsourcing.cipher.Cipher` objects.

The library's :class:`~eventsourcing.cipher.AESCipher` class
implements the abstract base class :class:`~eventsourcing.cipher.Cipher`.
It can be used to cryptographically encode and decode the state of stored
events using the `AES cipher <https://pycryptodome.readthedocs.io/en/stable/src/cipher/aes.html>`_
from the `PyCryptodome library <https://pycryptodome.readthedocs.io/en/stable/index.html>`_
in `GCM mode <https://pycryptodome.readthedocs.io/en/stable/src/cipher/modern.html#gcm-mode>`_.
AES is a very fast and secure symmetric block cipher, and is the de facto
standard for symmetric encryption. Galois/Counter Mode (GCM) is a mode of
operation for symmetric block ciphers that is designed to provide both data
authenticity and confidentiality, and is widely adopted for its performance.

A :class:`~eventsourcing.cipher.Cipher` is constructed with an
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

    key = AESCipher.create_key(num_bytes=32) # 16, 24, or 32
    environment = Environment()
    environment["CIPHER_KEY"] = key
    cipher = AESCipher(environment)

    mapper = Mapper(
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
class class:`~eventsourcing.cipher.Cipher`.


Compression and encryption
==========================

Stored events can be both compressed and encrypted.

.. code-block:: python

    mapper = Mapper(
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

.. code-block:: python

    from eventsourcing.persistence import EventStore

    event_store = EventStore(
        mapper=mapper,
        recorder=application_recorder,
    )

    event_store.put([domain_event])

    domain_events = list(event_store.get(id1))
    assert domain_events == [domain_event]


.. _Factory:

Infrastructure factory
======================

An infrastructure factory helps with the construction of all the
persistence infrastructure objects mentioned above.

The library's :class:`~eventsourcing.persistence.InfrastructureFactory` class
is an abstract base class for infrastructure factories. It provides a
standard way for applications to select and construct persistence
infrastructure classes from persistence modules. Each persistence
module has a concrete infrastructure factory.

.. code-block:: python

    from eventsourcing.persistence import InfrastructureFactory


The class method :func:`~eventsourcing.persistence.InfrastructureFactory.construct`
will construct a concrete infrastructure factory from a persistence module. Set the
environment variable ``PERSISTENCE_MODULE`` to the :ref:`topic <Topics>` of a
persistence module to select which persistence module to use. By default, it will
construct the infrastructure factory from the library's :ref:`"plain old Python
objects" persistence module <popo-module>`.

.. code-block:: python

    environ = Environment()
    environ["PERSISTENCE_MODULE"] = "eventsourcing.popo"
    factory = InfrastructureFactory.construct(environ)

    assert factory.__class__.__module__ == "eventsourcing.popo"


The method :func:`~eventsourcing.persistence.InfrastructureFactory.aggregate_recorder`
will construct an "aggregate recorder" from the selected persistence module.

.. code-block:: python

    recorder = factory.aggregate_recorder()

    assert isinstance(recorder, AggregateRecorder)
    assert recorder.__class__.__module__ == "eventsourcing.popo"

The method :func:`~eventsourcing.persistence.InfrastructureFactory.application_recorder`
will construct an "application recorder" from the selected persistence module.

.. code-block:: python

    recorder = factory.application_recorder()

    assert isinstance(recorder, ApplicationRecorder)
    assert recorder.__class__.__module__ == "eventsourcing.popo"

The method :func:`~eventsourcing.persistence.InfrastructureFactory.process_recorder`
will construct a "process recorder" from the selected persistence module.

.. code-block:: python

    recorder = factory.process_recorder()

    assert isinstance(recorder, ProcessRecorder)
    assert recorder.__class__.__module__ == "eventsourcing.popo"

The method :func:`~eventsourcing.persistence.InfrastructureFactory.transcoder`
will construct a transcoder object.

.. code-block:: python

    transcoder = factory.transcoder()
    transcoder.register(UUIDAsHex())
    transcoder.register(DatetimeAsISO())
    transcoder.register(DateAsISO())
    transcoder.register(ComplexCustomValueAsDict())
    transcoder.register(SimpleCustomValueAsDict())

The method :func:`~eventsourcing.persistence.InfrastructureFactory.mapper`
will construct a mapper object.

.. code-block:: python

    mapper = factory.mapper(transcoder=transcoder)

The method :func:`~eventsourcing.persistence.InfrastructureFactory.event_store`
will construct an event store object.

.. code-block:: python


    event_store = factory.event_store(
        mapper=mapper,
        recorder=recorder,
    )

The event store can be used to put and get domain events.

.. code-block:: python

    event_store.put([domain_event])
    domain_events = list(event_store.get(id1))

    assert domain_events == [domain_event]

Environment variables can be used to select and configure persistence infrastructure.
In this way, an event-sourced application :ref:`can be easily configured <Persistence>`
in different ways at different times. For example, the optional environment variables
``COMPRESSOR_TOPIC``, ``CIPHER_TOPIC``, and ``CIPHER_KEY`` may be used to enable
compression and encryption of stored events. Different persistence modules use their
own particular set of environment variables, of which some are required and some are
optional.

.. _sqlite-module:

SQLite module
=============

The persistence module :mod:`eventsourcing.sqlite` supports recording events in
`SQLite <https://www.sqlite.org/>`_. Recorder classes use the Python :mod:`sqlite3`
module. The direct use of the library's SQLite recorders is shown below.

.. code-block:: python

    # SQLiteAggregateRecorder
    from eventsourcing.sqlite import SQLiteAggregateRecorder
    from eventsourcing.sqlite import SQLiteDatastore

    datastore = SQLiteDatastore(db_name=":memory:")
    aggregate_recorder = SQLiteAggregateRecorder(datastore, "stored_events")
    aggregate_recorder.create_table()
    aggregate_recorder.insert_events([stored_event])

    recorded_events = aggregate_recorder.select_events(stored_event.originator_id)
    assert recorded_events[0] == stored_event, (recorded_events[0], stored_event)

    # SQLiteApplicationRecorder
    from eventsourcing.sqlite import SQLiteApplicationRecorder
    datastore = SQLiteDatastore(db_name=":memory:")
    application_recorder = SQLiteApplicationRecorder(datastore)
    application_recorder.create_table()
    application_recorder.insert_events([stored_event])

    recorded_events = application_recorder.select_events(stored_event.originator_id)
    assert recorded_events[0] == stored_event

    notifications = application_recorder.select_notifications(start=1, limit=10)
    assert notifications[0].id == 1
    assert notifications[0].originator_id == stored_event.originator_id
    assert notifications[0].originator_version == stored_event.originator_version

    # SQLiteProcessRecorder
    from eventsourcing.sqlite import SQLiteProcessRecorder
    datastore = SQLiteDatastore(db_name=":memory:")
    process_recorder = SQLiteProcessRecorder(datastore)
    process_recorder.create_table()
    process_recorder.insert_events([stored_event], tracking=tracking)

    recorded_events = process_recorder.select_events(stored_event.originator_id)
    assert recorded_events[0] == stored_event

    notifications = process_recorder.select_notifications(start=1, limit=10)
    assert notifications[0].id == 1
    assert notifications[0].originator_id == stored_event.originator_id
    assert notifications[0].originator_version == stored_event.originator_version
    assert process_recorder.max_tracking_id("upstream") == 21


More commonly, the infrastructure factory is used to construct persistence
infrastructure objects. The persistence module :mod:`eventsourcing.sqlite`
supports the standard infrastructure factory interface. The SQLite persistence
module can be selected and configured with environment variables.

.. code-block:: python

    environ = Environment()
    environ["PERSISTENCE_MODULE"] = "eventsourcing.sqlite"
    environ["SQLITE_DBNAME"] = ":memory:"
    environ["SQLITE_LOCK_TIMEOUT"] = "10"


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

    assert factory.__class__.__module__ == "eventsourcing.sqlite"
    assert recorder.__class__.__module__ == "eventsourcing.sqlite"

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


.. _postgres-module:

PostgreSQL module
=================

The persistence module :mod:`eventsourcing.postgres` supports storing events in
`PostgresSQL <https://www.postgresql.org/>`_ using the third party :mod:`psycopg2`
module.

.. code-block:: python

    environ = Environment()
    environ["PERSISTENCE_MODULE"] = "eventsourcing.postgres"

The library's PostgreSQL :class:`~eventsourcing.postgres.Factory` also uses various
environment variables to control the construction and configuration of its persistence
infrastructure.

.. code-block:: python

    environ["POSTGRES_DBNAME"] = "eventsourcing"
    environ["POSTGRES_HOST"] = "127.0.0.1"
    environ["POSTGRES_PORT"] = "5432"
    environ["POSTGRES_USER"] = "eventsourcing"
    environ["POSTGRES_PASSWORD"] = "eventsourcing"
    environ["POSTGRES_CONNECT_TIMEOUT"] = "5"
    environ["POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT"] = "5"
    environ["POSTGRES_POOL_SIZE"] = "5"
    environ["POSTGRES_MAX_OVERFLOW"] = "10"
    environ["POSTGRES_CONN_MAX_AGE"] = ""
    environ["POSTGRES_PRE_PING"] = "n"
    environ["POSTGRES_POOL_TIMEOUT"] = "30"
    environ["POSTGRES_LOCK_TIMEOUT"] = "5"
    environ["POSTGRES_SCHEMA"] = "public"


The environment variables ``POSTGRES_DBNAME``, ``POSTGRES_HOST``, ``POSTGRES_PORT``,
``POSTGRES_USER``, and ``POSTGRES_PASSWORD`` are required to set the name of a database,
the database server's host name and port number, and the database user name and password.

The optional environment variable ``POSTGRES_CONNECT_TIMEOUT`` may be used to timeout
attempts to create new database connections. If set, an integer value is required.
The default value is 5.

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

The optional environment variable ``POSTGRES_POOL_TIMEOUT`` may be used to control how many seconds
to wait before raising a "pool exhausted" exception for a connection to be returned to a pool that
has already opened the maximum number of connections configured by ``POSTGRES_POOL_SIZE`` and
``POSTGRES_MAX_OVERFLOW``. If set, a floating point number is required. The default value is 30.

The optional environment variable ``POSTGRES_CONN_MAX_AGE`` is used to control the length of time in
seconds before a connection is closed. By default this value is not set, and connections will
be reused indefinitely, until an operational database error is encountered, or the connection
is returned to a pool that is full. If this value is set to a positive integer, the connection
will be closed after this number of seconds from the time it was created, but only when the
connection is not in use after the connection has been returned to the pool. If this value if
set to zero, each connection will only be used once. Setting this value to an empty string has
the same effect as not setting this value. Setting this value to any other value will cause an
environment error exception to be raised. If your database terminates idle connections after some
time, you should set ``POSTGRES_CONN_MAX_AGE`` to a lower value, so that attempts are not made to
use connections that have been terminated by the database server, and so that your connections are
not suddenly terminated in the middle of a transaction.

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
    from eventsourcing.tests.persistence_tests.test_postgres import drop_postgres_table
    factory = InfrastructureFactory.construct(environ)
    drop_postgres_table(factory.datastore, "stored_events")
    del factory


.. code-block:: python

    factory = InfrastructureFactory.construct(environ)
    recorder = factory.application_recorder()

    assert factory.__class__.__module__ == "eventsourcing.postgres"
    assert recorder.__class__.__module__ == "eventsourcing.postgres"

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

.. _other-persistence-modules:

Other persistence modules
=========================

Other persistence modules are available or under development. There are
`extension projects <https://github.com/pyeventsourcing>`_
that support using popular ORMs for persistence such as
`Django <https://github.com/pyeventsourcing/eventsourcing-django#readme>`_
and `SQLAlchemy <https://github.com/pyeventsourcing/eventsourcing-sqlalchemy#readme>`_,
specialist event stores such as
`Axon Server <https://github.com/pyeventsourcing/eventsourcing-axonserver#readme>`_
and `EventStoreDB <https://github.com/pyeventsourcing/eventsourcing-eventstoredb#readme>`_,
and popular NoSQL databases such as
`DynamoDB <https://github.com/pyeventsourcing/eventsourcing-dynamodb#readme>`_.


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
