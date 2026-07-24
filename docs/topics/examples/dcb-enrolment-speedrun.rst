.. _DCB example 5:

DCB 5 - Speedrun
================

A "speedrun" script has been written, to help compare different event stores for dynamic consistency boundaries.
It iterates over a sequence of operations using the :ref:`enrolment interface <Enrolment interface>`. In each iteration, 10 students and 10 courses are registered, and then
all the students are enrolled on all the courses. That gives 120 operations per iteration. It prints the number of
operations completed in each second, alongside the total number of operations completed so far.

We wil firstly baseline the performance by using :ref:`event-sourced aggregates <Aggregates and DCB>`
and then trial the different persistence infrastructure we have developed for our :doc:`DCB application </topics/examples/dcb-enrolment-with-basic-objects>`.

Whilst this "speedrun" does not give an indication of the performance under concurrent load or the performance
with high volumes of recorded events, the scenario of a single client making sequential requests for a sustained
period of time does measure the performance of the basic and essential operations of reading and writing.

Event-sourced aggregates
------------------------

Firstly, let's baseline performance benchmarks by running the example :ref:`Aggregates and DCB <Aggregates and DCB>`.

.. code-block::

 Dynamic Consistency Boundaries Speed Run: Course Subscriptions
 ==============================================================

 Per iteration: 10 courses, 10 students (120 ops)

 Running 'agg-pg' mode: EnrolmentWithAggregates
     PERSISTENCE_MODULE: eventsourcing.postgres
     POSTGRES_DBNAME: course_subscriptions_speedrun
     POSTGRES_HOST: 127.0.0.1
     POSTGRES_PORT: 5432
     POSTGRES_USER: eventsourcing
     POSTGRES_PASSWORD: eventsourcing
     POSTGRES_ENABLE_DB_FUNCTIONS: y
     POSTGRES_POOL_SIZE: 1
     POSTGRES_MAX_OVERFLOW: 0
     POSTGRES_MAX_WAITING: 0

 Events in database at start:  0 events

 Stopping after: 20s

 [0:00:01s]        25 iterations      3000 ops      342 μs/op    2918 ops/s
 [0:00:02s]        51 iterations      6120 ops      321 μs/op    3110 ops/s
 [0:00:03s]        77 iterations      9240 ops      318 μs/op    3141 ops/s
 [0:00:04s]       103 iterations     12360 ops      317 μs/op    3145 ops/s
 [0:00:05s]       129 iterations     15480 ops      317 μs/op    3149 ops/s
 [0:00:06s]       155 iterations     18600 ops      319 μs/op    3129 ops/s
 [0:00:07s]       181 iterations     21720 ops      320 μs/op    3122 ops/s
 [0:00:08s]       207 iterations     24840 ops      319 μs/op    3128 ops/s
 [0:00:09s]       233 iterations     27960 ops      324 μs/op    3080 ops/s
 [0:00:10s]       259 iterations     31080 ops      321 μs/op    3115 ops/s
 [0:00:11s]       285 iterations     34200 ops      320 μs/op    3122 ops/s
 [0:00:12s]       311 iterations     37320 ops      319 μs/op    3125 ops/s
 [0:00:13s]       337 iterations     40440 ops      321 μs/op    3113 ops/s
 [0:00:14s]       363 iterations     43560 ops      320 μs/op    3122 ops/s
 [0:00:15s]       390 iterations     46800 ops      314 μs/op    3181 ops/s
 [0:00:16s]       417 iterations     50040 ops      304 μs/op    3280 ops/s
 [0:00:17s]       444 iterations     53280 ops      313 μs/op    3189 ops/s
 [0:00:18s]       470 iterations     56400 ops      315 μs/op    3165 ops/s
 [0:00:19s]       496 iterations     59520 ops      315 μs/op    3171 ops/s
 [0:00:20s]       523 iterations     62760 ops      315 μs/op    3169 ops/s

 Events in database at end:  115,060 events  (115,060 new, 5,745/s)

The performance report for event-sourced aggregates accomplished 62,760 operations in 20s.
That gives an average of 0.319 milliseconds per operation, and a target for implementing DCB.

PostgreSQL with GIN index
-------------------------


The :class:`~examples.coursebookingdcb.postgres_ts.PostgresDcbRecorderTS` was our second attempt to
implement the challenging DCB query logic in way that is performant. The first attempt used an array
column for tags, and array operators to search for types and tags. It simply didn't work very well,
grinding to a virtual halt after only a modest volume of recorded events.

In this implementation, the complex DCB query logic is implemented using PostgreSQL's "full text search"
(FTS) functionality, ``tsvector`` and ``tsquery``, and a GIN index.

Types and tags of a DCB event are prefixed and concatenated into a ``tsvector`` string. A set of DCB
query items is similarly compounded into a ``tsquery`` that expresses the DCB query logic. Database
functions for appending and selecting events are defined, and a custom composite type is defined for
efficiently sending an array of DCB events to the database.

In this way, both the read and the append operations of this DCB event store can be executed as fast
as possible with a single database round-trip.

The performance of the Postgres implementation using "full text search" is shown below.

.. code-block::

 Dynamic Consistency Boundaries Speed Run: Course Subscriptions
 ==============================================================

 Per iteration: 10 courses, 10 students (120 ops)

 Running 'dcb-pg-ts' mode: EnrolmentWithBasicDcbObjects
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
might perform well in a heavy production environment.


PostgreSQL with B+trees and CTEs
--------------------------------

The performance of the :ref:`Postgres DCB recorder <Postgres DCB recorder>` is reported below.

.. code-block::

 Dynamic Consistency Boundaries Speed Run: Course Subscriptions
 ==============================================================

 Per iteration: 10 courses, 10 students (120 ops)

 Running 'dcb-pg-tt' mode: EnrolmentWithBasicDcbObjects
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
with event-sourced aggregates.


UmaDB
-----

The performance of the :ref:`UmaDB DCB recorder <UmaDB DCB recorder>` is reported below.

.. code-block::

 Dynamic Consistency Boundaries Speed Run: Course Subscriptions
 ==============================================================

 Per iteration: 10 courses, 10 students (120 ops)

 Running 'dcb-umadb' mode: EnrolmentWithBasicDcbObjects
     PERSISTENCE_MODULE: eventsourcing_umadb
     UMADB_URI: http://127.0.0.1:50051

 Events in database at start:  0 events

 Stopping after: 20s

 [0:00:01s]        38 iterations      4560 ops      221 μs/op    4511 ops/s
 [0:00:02s]        71 iterations      8520 ops      252 μs/op    3960 ops/s
 [0:00:03s]       104 iterations     12480 ops      256 μs/op    3893 ops/s
 [0:00:04s]       136 iterations     16320 ops      257 μs/op    3888 ops/s
 [0:00:05s]       168 iterations     20160 ops      258 μs/op    3870 ops/s
 [0:00:06s]       202 iterations     24240 ops      249 μs/op    4009 ops/s
 [0:00:07s]       235 iterations     28200 ops      249 μs/op    4003 ops/s
 [0:00:08s]       268 iterations     32160 ops      249 μs/op    4000 ops/s
 [0:00:09s]       301 iterations     36120 ops      252 μs/op    3966 ops/s
 [0:00:10s]       335 iterations     40200 ops      251 μs/op    3976 ops/s
 [0:00:11s]       366 iterations     43920 ops      263 μs/op    3792 ops/s
 [0:00:12s]       398 iterations     47760 ops      266 μs/op    3755 ops/s
 [0:00:13s]       429 iterations     51480 ops      266 μs/op    3753 ops/s
 [0:00:14s]       460 iterations     55200 ops      264 μs/op    3778 ops/s
 [0:00:15s]       492 iterations     59040 ops      261 μs/op    3820 ops/s
 [0:00:16s]       524 iterations     62880 ops      257 μs/op    3879 ops/s
 [0:00:17s]       557 iterations     66840 ops      259 μs/op    3852 ops/s
 [0:00:18s]       589 iterations     70680 ops      259 μs/op    3846 ops/s
 [0:00:19s]       620 iterations     74400 ops      263 μs/op    3797 ops/s
 [0:00:20s]       651 iterations     78120 ops      268 μs/op    3728 ops/s

 Events in database at end:  78,120 events  (78,120 new, 3,904/s)

This implementation is much faster than the best we could achieve with PostgreSQL, and
marginally out-performs event-sourced aggregates for the single-threaded scenario. With
large volumes of data, and with high-concurrency, UmaDB out-performs PostgreSQL by several
factors.

Having successfully addressed the technical challenge of implementing the complex query logic of DCB,
we feel confident in recommending DCB as a strong alternative to the "traditional" event-sourced aggregates.

However, it should be remembered that aggregates were originally introduced because of the conceptual
overhead of dynamic consistency boundaries before Domain Driven Design.

Summary
-------

The table below summarises the speedrun results.

+---------------------------------+---------+----------+
| Persistence module              |  Ops/s  | relative |
+=================================+=========+==========+
| Event-sourced aggregates        |  3138   |   1.00   |
+---------------------------------+---------+----------+
| DCB with Postgres (GIN index)   |   392   |   0.12   |
+---------------------------------+---------+----------+
| DCB with Postgres (B+trees)     |  2880   |   0.92   |
+---------------------------------+---------+----------+
| DCB with UmaDB                  |  3904   |   1.24   |
+---------------------------------+---------+----------+
