.. _UmaDB:

DCB with UmaDB
==============

`UmaDB <https://umadb.io>`_ is a specialist event store for DCB, which directly implements in Rust the
:doc:`same approach </topics/examples/coursebooking-dcb-postgres-tt>` used to implement
DCB in PostgreSQL in the previous example.

The Python module ``eventsourcing-umadb`` used in the speedrun below `adapts the
Python client for UmaDB <https://pypi.org/project/eventsourcing-umadb/>`_.

Speedrun
--------

The performance of UmaDB running with the :doc:`course subscription challenge </topics/examples/coursebooking>`
is reported below.

.. code-block::

 Dynamic Consistency Boundaries Speed Run: Course Subscriptions
 ==============================================================

 Per iteration: 10 courses, 10 students (120 ops)

 Running 'dcb-umadb' mode: EnrolmentWithDCB
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

This implementation is marginally faster than event-sourced aggregates for the single-threaded scenario.
With large volumes of data, and with high-concurrency, UmaDB out-performs PostgreSQL by several factors.

Having successfully addressed the technical challenge of implementing the complex query logic of DCB, let's
turn our attention to higher-level abstractions that are perhaps more usable than coding with the basic DCB
objects. The examples :doc:`Enduring Objects and Groups </topics/examples/coursebooking-dcb-refactored>`
and :doc:`Vertical Slices with DCB </topics/examples/coursebooking-dcb-slices>` present some alternatives.
