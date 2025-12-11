.. _DCB PostgreSQL TT:

Fast PostgreSQL DCB
===================

On this page we have another attempt to implement the complex DCB query logic in a way that is more performant.

The first attempt used array columns and array operators. The second attempt used text search.
Both of these first two attempts gave poor results. The third attempt, explained below, gives
much better results.

This library now includes this version of the Postgres DCB recorder.

Postgres DCB recorder v3
------------------------

The general idea motivating this third design is the observation that tags follow from individual enduring
objects in the real world, and therefore typically to have high cardinality, and therefore to be highly
selective in queries. On the other hand, event types are expected to follow from types of software object
classes, and therefore to have low cardinality. Mixing these up in a select statement can cause the query
planner to find sub-optimal solution.

The design for this implementation focuses on selecting by tags first, using a B-tree index on a secondary
table of tags, and then filtering by position and type. The sequence positions on the main table are also indexed
with a B-tree that "covers" the type column. In this way, recorded events can be selected by tag and filtered by
type, and ordered and limited, for a set of DCB query items, using only B-tree indexes, without touching the
main table of recorded events.

Conditional append operations use a stored procedure with a "fail condition" CTE and an "unconditional append" CTE
insert statement. Having a stored procedure with two separate CTE statements allows each part of the function
to be planned separately. Executing these two statements in a stored procedure means conditional append operations
can be performed efficiently with one round-trip. The Python code passes lists of DCB query items and lists of DCB
events as composite arrays of custom types. Logging execution times directly from the database shows that the database typically executes the
stored procedure for conditional appends in 100-200 μs with millions of recorded events. A multi-clause CTE statement
is also used to select events for read operations. This is executed as a prepared statement.

The :class:`~eventsourcing.dcb.postgres_tt.PostgresDCBRecorderTT` class shown below implements
:class:`~eventsourcing.dcb.api.DCBRecorder` using this approach.

.. literalinclude:: ../../../eventsourcing/dcb/postgres_tt.py
    :start-at: DB_TYPE_NAME
    :end-before: PostgresTTDCBFactory

Speedrun
--------

The performance of :class:`~eventsourcing.dcb.postgres_tt.PostgresDCBRecorderTT` is reported below.

.. code-block::

 Dynamic Consistency Boundaries Speed Run: Course Subscriptions
 ==============================================================

 Per iteration: 10 courses, 10 students (120 ops)

 Running 'dcb-pg-tt' mode: EnrolmentWithDCB
     PERSISTENCE_MODULE: eventsourcing.dcb.postgres_tt
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

 [0:00:01s]        22 iterations      2640 ops      382 μs/op    2615 ops/s
 [0:00:02s]        47 iterations      5640 ops      341 μs/op    2932 ops/s
 [0:00:03s]        71 iterations      8520 ops      340 μs/op    2933 ops/s
 [0:00:04s]        96 iterations     11520 ops      341 μs/op    2924 ops/s
 [0:00:05s]       120 iterations     14400 ops      343 μs/op    2909 ops/s
 [0:00:06s]       144 iterations     17280 ops      344 μs/op    2902 ops/s
 [0:00:07s]       168 iterations     20160 ops      346 μs/op    2889 ops/s
 [0:00:08s]       192 iterations     23040 ops      345 μs/op    2891 ops/s
 [0:00:09s]       216 iterations     25920 ops      344 μs/op    2899 ops/s
 [0:00:10s]       240 iterations     28800 ops      344 μs/op    2900 ops/s
 [0:00:11s]       265 iterations     31800 ops      344 μs/op    2902 ops/s
 [0:00:12s]       289 iterations     34680 ops      345 μs/op    2894 ops/s
 [0:00:13s]       313 iterations     37560 ops      346 μs/op    2883 ops/s
 [0:00:14s]       337 iterations     40440 ops      345 μs/op    2890 ops/s
 [0:00:15s]       361 iterations     43320 ops      348 μs/op    2873 ops/s
 [0:00:16s]       385 iterations     46200 ops      347 μs/op    2876 ops/s
 [0:00:17s]       409 iterations     49080 ops      346 μs/op    2890 ops/s
 [0:00:18s]       433 iterations     51960 ops      348 μs/op    2869 ops/s
 [0:00:19s]       457 iterations     54840 ops      349 μs/op    2864 ops/s
 [0:00:20s]       481 iterations     57720 ops      348 μs/op    2872 ops/s

 Events in database at end:  57,720 events  (57,720 new, 2,880/s)

With sub-millisecond application command response times, this implementation effectively closes the performance gap
with event-sourced aggregates. Let's see if we can do better by implementing the :doc:`same approach in Rust </topics/examples/coursebooking-dcb-umadb>`.

