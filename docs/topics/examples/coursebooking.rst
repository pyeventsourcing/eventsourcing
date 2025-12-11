.. _DCB example 1:

Course Subscriptions Challenge
==============================

The `course subscription challenge <https://dcb.events/examples/course-subscriptions/>`_ is
often used when discussing `dynamic consistency boundaries <https://dcb.events/>`_. The
challenge is to enforce a rule when enrolling students on courses that no student can join more
than a given number of courses, and no course can accept more than a given number of students.
The idea is that this is either difficult or impossible with "traditional" event-sourced aggregates
without much accidental complexity, and that DCB allows more straightforward implementations.

On this page, we are setting the scene by defining and validating an
interface and test case for the course subscriptions challenge. The test case will be satisfied first with
the standard "traditional" event-sourced aggregates. Over the next few pages, we will implement the course
subscriptions challenge again using the basic objects and methods described in the "dynamic consistency boundaries"
specification, and then again with some higher-level styles for DCB. Alongside these developments, we will also
develop successively better support for the technical challenge of implementing a DCB event store.

.. _Enrolment interface:

Enrolment interface
-------------------

The course subscriptions challenge can be expressed firstly as an interface.

The :class:`~examples.coursebooking.interface.EnrolmentInterface` will be used across
all the examples in the following pages. We have defined methods for registering students,
for registering courses, for joining students with courses, for listing students for
a course, and for listing courses for a student, along with some exception classes.

.. literalinclude:: ../../../examples/coursebooking/interface.py


Enrolment test case
-------------------

The :class:`~examples.coursebooking.test_enrolment.EnrolmentTestCase` below checks an implementation can register
students and courses, and that students can join courses, with some particular conditions that should lead to
particular errors.

.. literalinclude:: ../../../examples/coursebooking/test_enrolment.py
    :pyobject: EnrolmentTestCase


Aggregates and DCB
------------------

Before we continue with DCB, let's implement the course subscriptions challenge with "traditional" event-sourced
aggregates. This will allow us to validate the interface, to demonstrate the test case is effective, and to
baseline performance benchmarks.

The central critique motivating DCB is that the aggregates of DDD establish strict and rigid consistency
boundaries that may eventually become inappropriate and difficult to refactor. This may be true. We will
investigate later how comparatively easy or difficult it is to refactor sequences of events recorded by
DCB applications and by event-sourced applications.

Another of the arguments motivating DCB is that, `"by definition, the aggregate is the boundary of consistency"
<https://sara.event-thinking.io/2023/04/kill-aggregate-chapter-2-the-aggregate-does-not-fit-the-storytelling.html>`_
and so it is impossible to implement the "course subscriptions" challenge using event-sourced aggregates without
the accidental complexity of awkward tricks. As we shall see, this is not true.

Whatever the arguments are against aggregates, it is more important that a proposition be interesting than that
it be true. DCB is indeed an interesting novel proposition. We can return elsewhere to assessing and debating its
analysis of software development.

Event-sourced aggregates
------------------------

The domain model shown below defines :class:`~examples.coursebooking.domainmodel.Course`, an event-sourced aggregate
class for courses that students can join, and :class:`~examples.coursebooking.domainmodel.Student`, an event-sourced
aggregate class for students that may join courses.

.. literalinclude:: ../../../examples/coursebooking/domainmodel.py
    :pyobject: Course

.. literalinclude:: ../../../examples/coursebooking/domainmodel.py
    :pyobject: Student

These aggregate classes are implemented using the concise
:ref:`declarative syntax <Declarative syntax>` supported by this library. These aggregate classes are coded to use string IDs as demonstrated
in :doc:`example 11  </topics/examples/aggregate11>`.


Enrolment with aggregates
-------------------------

The :class:`~examples.coursebooking.application.EnrolmentWithAggregates` application uses
the :class:`~examples.coursebooking.domainmodel.Course` and :class:`~examples.coursebooking.domainmodel.Student`
aggregate classes to implement the :ref:`enrolment interface <Enrolment interface>`.
The "consistency boundary" for joining a course involves atomically recording new events from more
than one aggregate, the student and the course.

.. literalinclude:: ../../../examples/coursebooking/application.py
    :pyobject: EnrolmentWithAggregates

This meets the "course subscriptions" challenge with event-sourced aggregates, without tricks and without
accidental complexity. It shows that it is perfectly possible, entirely legitimate, and quite straightforward
to extend the transactional consistency boundary when using event-sourced aggregates to include more than one
aggregate. Indeed, this is a useful technique.


At the time of writing, this possibility is not mentioned in the list of
`traditional approaches <https://dcb.events/examples/course-subscriptions/#traditional-approaches>`_ on the dynamic
consistency boundaries website, which lists only three options: eventual consistency, larger aggregate, reservation
pattern.

Testing with aggregates
-----------------------

The test case below calls :func:`~examples.coursebooking.test_enrolment.EnrolmentTestCase.assert_implementation`
with an instance of :class:`~examples.coursebooking.application.EnrolmentWithAggregates`, configured to use an
in-memory event store and to use PostgreSQL. The third test method shows more explicitly that extending the
transactional consistency boundary when using event-sourced aggregates to include more than one aggregate is
technically sound, by checking that the recorded consistency of the course-student nexus is guarded against
concurrent operations.

.. literalinclude:: ../../../examples/coursebooking/test_application.py
    :pyobject: TestEnrolmentWithAggregates

Speedrun
--------

A "speedrun" script has been written, to help compare different implementations of the course subscriptions
challenge, and different implementations of event stores for dynamic consistency boundaries. It iterates over
a sequence of operations. In each iteration, 10 students and 10 courses are registered, and then all the students
are enrolled on all the courses. That gives 120 operations per iteration. It prints the number of operations
completed in each second, alongside the total number of operations completed so far.

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

The performance report for :class:`~examples.coursebooking.application.EnrolmentWithAggregates`
running with accomplished 62760 operations in 20s. That gives an average of 0.319
milliseconds per operation, and a target for implementing DCB.

Summary
-------

Implementing the course subscriptions challenge with "traditional" event-sourced aggregates was
straightforward. The application didn't have any accidental complexity and performed well.

The transactional consistency boundary can legitimately be extended in include more than one aggregate.
The meaning of "not less than" is "greater than or equal to". It has been a common misapprehension
that the "consistency boundary" notion in DDD is equal to one aggregate. The actual idea from DDD
is that a database transactional consistency boundary must not be less than one aggregate. A
consistency boundary that includes more than one aggregate, or indeed other things, has always
been permitted by DDD.

Nevertheless, there are other reasons why DCB is an interesting novel approach for event sourcing,
so let's continue by :doc:`implementing the specification </topics/examples/coursebooking-dcb>` directly.


Code reference
--------------

.. automodule:: examples.coursebooking.interface
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:
    :special-members: __init__

.. automodule:: examples.coursebooking.test_enrolment
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:
    :special-members: __init__

.. automodule:: examples.coursebooking.domainmodel
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:
    :special-members: __init__

.. automodule:: examples.coursebooking.application
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:
    :special-members: __init__

