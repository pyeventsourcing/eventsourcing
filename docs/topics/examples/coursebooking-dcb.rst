.. _DCB example 2:

The DCB Specification
=====================

This page introduces our implementation of the objects and method defined in the
`specification <https://dcb.events/specification/>`_ for "dynamic consistency boundaries".
This library supports DCB by including the DCB object presented here.

Below you can see how to implement the "course subscriptions" challenge in Python using these basic
DCB objects and methods. Whilst the code is relatively verbose, the DCB approach can be understood directly
without any extra abstractions. The later examples :doc:`Enduring Objects and Groups </topics/examples/coursebooking-dcb-refactored>`
and :doc:`Enduring Objects and Groups </topics/examples/coursebooking-dcb-slices>` present alternative
higher-level abstractions that are perhaps more usable.

.. _Introduction to DCB:

Introduction to DCB
-------------------

Dynamic consistency boundaries (DCB) is a new variant of event sourcing presented in a
`humorously provocative way <https://sara.event-thinking.io/2023/04/kill-aggregate-chapter-1-I-am-here-to-kill-the-aggregate.html>`_
as "killing the aggregate".

A novel scheme is proposed that uses a single sequence of events, an :ref:`application sequence <Overview>`
in the terminology of this library.

Each event in DCB has one "type", some "data", and any number of "tags".
Recorded events also have an assigned "position" in the sequence, and for this reason are referred to as
"sequenced events". They correspond to the :ref:`stored event <Stored event objects>` and
:ref:`notification <Notification objects>` objects previously defined in this library.

When reading events from a DCB event store, a reader can supply a DCB "query". A DCB query has
zero, one, or many DCB "query items". Each query item may have zero, one, or many "types", and zero, one, or many
"tags". Optionally, the reader can also specify a position in the sequence of recorded events after which events
should be selected.

An event is selected by the query if it is matched by any of the query items. An event is matched by a query item
if either the event's type is mentioned in the query item's collection of types, or if the query item has zero types,
but then only if the event's tags are a superset of the query item's tags.

In this way, a query item with more types will be more inclusive, and a query item with more tags will be more
restrictive. Each query item will tend to add events to the set of events selected by the query. However, if a
query has zero query items, or no query is provided when reading, then all events will be selected, optionally
after the specified position.

When writing new events to a DCB event store, a writer can supply an "append condition" to ensure consistency
of recorded state. An append condition can include a query to select conflicting events, and a position after
which the query should be applied.

If the append condition fails, because conflicting events have been recorded, then an "integrity error" is raised
by the event store and the new events are not recorded. Otherwise, if the append condition does not fail, then all
the new events are recorded. Each recorded event is assigned a monotonically increasing position in the application
sequence, and thereby becomes a "sequenced event".

A command method will usually read a selection of recorded events, and then project the events into a
"decision model", from which one or many new events will be generated. When a command method writes
new events, the same query used for reading can also be used the append condition query, and the highest
"last known position" at the time of reading can be used as the append condition position. The command
method's query, that is used both when reading a writing, therefore defines the "consistency boundary"
for the command.

The multi-dimensional possibilities offered by combining a set of different query items is impressive. However,
this presents a technical challenge when implementing support for DCB applications. Firstly, the selections of
events have to be correct for all possible sets of query items. But then also, it will be a technical challenge
to achieve performance times for DCB applications that is comparable to that enjoyed by "traditional" event-sourced
aggregates.

A sustained effort has been made to implement support for DCB is a way that is both correct and performant. As we
will see, at first an attempt was made to use GIN indexes in PostgreSQL, with both array operators
and then with text vectors and full text search techniques. Many others have tried this too, in different ways. It is
commonly experienced to be relatively slow. In consequence, an alternative implementation in PostgreSQL was developed
that uses B+trees with a separate table for tags. This was much faster, especially when coded with common table
expressions. Finally, the idea of using B+ trees with CTEs in PostgreSQL was distilled into a specialist DCB event
store written in Rust, now called `UmaDB <https://umadb.io>`_.

DCB Objects and Methods
-----------------------

Here we present an implementation in Python of the basic objects and methods for DCB that are
described in the specification and discussed in the :ref:`Introduction to DCB <Introduction to DCB>`
on the previous page.

The :class:`~eventsourcing.dcb.api.DCBRecorder` class corresponds to the notion "event store" in the DCB
specification. It defines the "read" and "append" methods described in the DCB specification.
Following the terminology in this library, we have used the term "recorder" here and reserve
the name "event store" for a higher-level class that deals with domain events.
There are two enhancements. The first enhancement is to return from :class:`int` from the
:func:`~eventsourcing.dcb.api.DCBRecorder.append` method. This supports returning the position of the
last appended event, so that systems implemented with CQRS can transition from a "write" view to an
eventually-consistent "read" view, and wait for new events to be processed, avoiding the stale
read model problem. The second enhancement is to support subscriptions, with the :func:`~eventsourcing.dcb.api.DCBRecorder.subscribe`
method, so that readers can continue receiving newly recorded events.

.. literalinclude:: ../../../eventsourcing/dcb/api.py
    :pyobject: DCBRecorder

The :func:`~eventsourcing.dcb.api.DCBRecorder.read` method returns a :class:`~eventsourcing.dcb.api.DCBReadResponse`,
which is a Python iterator that returns :class:`~eventsourcing.dcb.api.DCBSequencedEvent` objects.
It has a :data:`~eventsourcing.dcb.api.DCBReadResponse.head` property that allows a reader to obtain a
"last known position" that corresponds to the last recorded event in the database at the time of reading,
rather than the sequence number of the last event it receives. This gives a better value for subsequent
append conditions.

.. literalinclude:: ../../../eventsourcing/dcb/api.py
    :pyobject: DCBReadResponse

The :func:`~eventsourcing.dcb.api.DCBRecorder.subscribe` method returns a :class:`~eventsourcing.dcb.api.DCBSubscription`
object, which is a Python iterator that returns :class:`~eventsourcing.dcb.api.DCBSequencedEvent` objects. It
can be used as a context manager.

.. literalinclude:: ../../../eventsourcing/dcb/api.py
    :pyobject: DCBSubscription

These methods depend on various DCB objects: :class:`~eventsourcing.dcb.api.DCBQuery`,
:class:`~eventsourcing.dcb.api.DCBQueryItem`, :class:`~eventsourcing.dcb.api.DCBSequencedEvent`,
:class:`~eventsourcing.dcb.api.DCBEvent`, and :class:`~eventsourcing.dcb.api.DCBAppendCondition`.
All are implemented as Python data classes.


.. literalinclude:: ../../../eventsourcing/dcb/api.py
    :pyobject: DCBQuery

.. literalinclude:: ../../../eventsourcing/dcb/api.py
    :pyobject: DCBQueryItem

.. literalinclude:: ../../../eventsourcing/dcb/api.py
    :pyobject: DCBSequencedEvent

.. literalinclude:: ../../../eventsourcing/dcb/api.py
    :pyobject: DCBEvent

.. literalinclude:: ../../../eventsourcing/dcb/api.py
    :pyobject: DCBAppendCondition

Enrolment with DCB
------------------

The :class:`~examples.coursebookingdcb.application.EnrolmentWithDCB` application implements
:ref:`the enrolment interface <Enrolment interface>` introduced on the previous page, using the basic DCB
objects and methods introduced above.

.. literalinclude:: ../../../examples/coursebookingdcb/application.py
    :pyobject: EnrolmentWithDCB

Just like the library's original :ref:`application class <Application objects>`,
:class:`~eventsourcing.dcb.application.DCBApplication` selects and constructs a concrete
DCB recorder implementation, according to its environment variable configuration.
This means we can easily run the application with different persistence infrastructure.


In-memory DCB recorder
----------------------

Before we can test this implementation of the :ref:`enrolment interface <Enrolment interface>`,
we need to implement at least one :class:`~eventsourcing.dcb.api.DCBRecorder`.

The :class:`~eventsourcing.dcb.popo.InMemoryDCBRecorder` class implements the :class:`~eventsourcing.dcb.api.DCBRecorder`
interface using only Python objects. You can see the query logic for selecting events implemented with nested
generator expressions, and the append condition logic that is implemented in the append method. DCB
events are stored in memory, and "deep copied" when appending and when reading to avoid any corruption
of sequenced events.

.. literalinclude:: ../../../eventsourcing/dcb/popo.py
    :pyobject: InMemoryDCBRecorder


Postgres DCB recorder
---------------------

As shown in :class:`~examples.coursebookingdcb.postgres_ts.PostgresDCBRecorderTS` below, we have also
implemented the complex DCB query logic in Postgres using "full text search" (FTS) functionality,
``tsvector`` and ``tsquery``, and a GIN index.

This is our second attempt to implement the challenging DCB query logic in way that is performant.
The first attempt used an array column for tags, and array operators to search for types and tags.
It simply didn't work very well, grinding to a virtual halt after only a modest volume of recorded
events.

In this implementation of the complex DCB query logic, the type and tags of a DCB event are prefixed
and concatenated into a ``tsvector`` string. A set of DCB query items is similarly compounded into a
``tsquery`` that expresses the DCB query logic. Database functions for appending and selecting events
are defined, and a custom composite type is defined for efficiently sending an array of DCB events to
the database.

In this way, both the read and the append operations of this DCB event store can be executed as fast
as possible with a single database round-trip.

.. literalinclude:: ../../../examples/coursebookingdcb/postgres_ts.py
    :pyobject: PostgresDCBRecorderTS

Testing with DCB
----------------

The test case is the same enrolment test case used in the :doc:`previous example </topics/examples/coursebooking>`,
but this time executed with the :class:`~examples.coursebookingdcb.application.EnrolmentWithDCB` class above rather than
:class:`~examples.coursebooking.application.EnrolmentWithAggregates`. The test method is run twice, once with the
in-memory implementation of the DCB event store, and again using the "full text search" PostgreSQL DCB implementation.

.. literalinclude:: ../../../examples/coursebookingdcb/test_application.py
    :pyobject: TestEnrolmentWithDCB


Performance with FTS
--------------------

The performance of the Postgres implementation using "full text search" is shown below.

.. code-block::

 Dynamic Consistency Boundaries Speed Run: Course Subscriptions
 ==============================================================

 Per iteration: 10 courses, 10 students (120 ops)

 Running 'dcb-pg-ts' mode: EnrolmentWithDCB
     PERSISTENCE_MODULE: examples.coursebookingdcb.postgres_ts
     POSTGRES_DBNAME: course_subscriptions_speedrun
     POSTGRES_HOST: 127.0.0.1
     POSTGRES_PORT: 5432
     POSTGRES_USER: eventsourcing
     POSTGRES_PASSWORD: eventsourcing
     POSTGRES_POOL_SIZE: 1
     POSTGRES_MAX_OVERFLOW: 0
     POSTGRES_MAX_WAITING: 0

 Events in database at start:  0 events

 Stopping after: 20s

 [0:00:01s]        18 iterations      2160 ops      466 μs/op    2144 ops/s
 [0:00:02s]        30 iterations      3600 ops      733 μs/op    1362 ops/s
 [0:00:03s]        38 iterations      4560 ops     1031 μs/op     969 ops/s
 [0:00:04s]        43 iterations      5160 ops     1702 μs/op     587 ops/s
 [0:00:05s]        45 iterations      5400 ops     3969 μs/op     251 ops/s
 [0:00:06s]        47 iterations      5640 ops     6921 μs/op     144 ops/s
 [0:00:07s]        48 iterations      5760 ops     6109 μs/op     163 ops/s
 [0:00:08s]        49 iterations      5880 ops     5208 μs/op     192 ops/s
 [0:00:09s]        51 iterations      6120 ops     7339 μs/op     136 ops/s
 [0:00:10s]        52 iterations      6240 ops     5658 μs/op     176 ops/s
 [0:00:11s]        53 iterations      6360 ops     6757 μs/op     147 ops/s
 [0:00:12s]        55 iterations      6600 ops     4750 μs/op     210 ops/s
 [0:00:13s]        56 iterations      6720 ops     4761 μs/op     210 ops/s
 [0:00:14s]        58 iterations      6960 ops     5699 μs/op     175 ops/s
 [0:00:15s]        60 iterations      7200 ops     5079 μs/op     196 ops/s
 [0:00:16s]        61 iterations      7320 ops     4934 μs/op     202 ops/s
 [0:00:17s]        63 iterations      7560 ops     6025 μs/op     165 ops/s
 [0:00:18s]        64 iterations      7680 ops     5933 μs/op     168 ops/s
 [0:00:19s]        65 iterations      7800 ops     5659 μs/op     176 ops/s
 [0:00:20s]        67 iterations      8040 ops     5956 μs/op     167 ops/s

 Events in database at end:  8,040 events  (8,040 new, 392/s)

Before we discuss the performance, let's consider the number of new events. The "one fact magic" of DCB can be
seen by looking at the number of new events at the end of the report (8,040). The number of new events is exactly
the same as the number of completed application operations. If you look again at the speedrun report for event-sourced
aggregates, you will see there are quite a lot more events recorded than actual operations. That's because the
event-sourced aggregates solution to the course subscriptions challenge generates two events each time a student
joins a course, one from the student aggregate, and one from the course aggregate. With the "one fact magic" of
DCB there is just one cross-cutting event.

Now let's consider the performance. It wasn't as terrible as the first attempt using array columns and array operator.
But it doesn't compare very well to the event-sourced aggregates. It accomplished 8,040 operations in 20s, giving an
average of 2.49 milliseconds per operation. The event-sourced aggregates application completed 62,760 in the same time.

However, the performance falls steeply after only a few thousand recorded events, and becomes approximately 20x slower
than the event-sourced aggregates in the previous example in a short time. This performance, of a few milliseconds per
operation, might sound acceptable. However, as the volume of recorded events increases, the performance steadily becomes
worse, decreasing to only a few operations per second with 5 million stored events. This is expected from
the "full text search" functionality and GIN indexes more generally.

Clearly if DCB is to be a viable approach to developing business software, we will need to
rethink how it might be possible to implement the complex DCB query logic in a way that
might perform well in a heavy production environment. Let's see what we can do in the
:doc:`next examples </topics/examples/coursebooking-dcb-postgres-tt>`.
