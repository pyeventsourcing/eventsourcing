.. _DCB example 1:

DCB 1 - Course Subscriptions
============================

On this page, we are setting the scene for a series of examples that illustrate the support offered
by this library for "dynamic consistency boundaries".

We will define and validate a test case and an interface for the course subscriptions challenge. Over
the next few pages, we will explore the basic objects and methods described in the "dynamic consistency
boundaries" specification, and then look at some higher-level styles for Dcb. Alongside these developments,
we will also present an assessment of successively better support for the technical challenge of
implementing a DCB event store.

Introduction
------------

The `course subscription challenge <https://dcb.events/examples/course-subscriptions/>`_ is
often used when discussing `dynamic consistency boundaries <https://dcb.events/>`_. The
challenge is to enforce a rule when enrolling students on courses that no student can join more
than a given number of courses, and no course can accept more than a given number of students.
The idea is that this is either difficult or impossible with "traditional" event-sourced aggregates
without much accidental complexity, and that DCB allows more straightforward implementations.

In the section :ref:`Aggregates and DCB <Aggregates and Dcb>` we can see how to implement the course
subscriptions challenge using "traditional" event-sourced aggregates, by extending the consistency
boundary to include more than one aggregate. In the :doc:`Basic DCB Objects example </topics/examples/dcb-enrolment-with-basic-objects>`, you can see how to
implement the "course subscriptions" challenge in Python using these basic :ref:`DCB objects <DCB objects>`. Whilst the
code is relatively verbose, the DCB approach can be understood directly
without any extra abstractions. The later examples :doc:`Enduring Objects and Groups </topics/examples/dcb-enrolment-with-enduring-objects>`
and :doc:`Vertical Slices with DCB </topics/examples/dcb-enrolment-with-vertical-slices>` present the alternative
higher-level abstractions supported by this library that are perhaps more usable.

.. _Enrolment test case:

Enrolment test case
-------------------

The :class:`~examples.dcb_enrolment.test_enrolment.EnrolmentTestCase` below checks an implementation can register
students and courses, and that students can join courses, with some particular conditions that should lead to
particular errors. It depends on the :ref:`Enrolment interface <Enrolment interface>` defined below.

.. literalinclude:: ../../../examples/dcb_enrolment/test_enrolment.py
    :pyobject: EnrolmentTestCase


.. _Enrolment interface:

Enrolment interface
-------------------

The course subscriptions challenge can be expressed firstly as an interface.

The :class:`~examples.dcb_enrolment.interface.EnrolmentInterface` will be used across
all the examples in the following pages. We have defined methods for registering students,
for registering courses, for joining students with courses, for listing students for
a course, and for listing courses for a student, along with some exception classes.

.. literalinclude:: ../../../examples/dcb_enrolment/interface.py


.. _Aggregates and Dcb:

Aggregates and Dcb
------------------

Before we continue with Dcb, let's implement the course subscriptions challenge with "traditional" event-sourced
aggregates. This will allow us to validate the interface and to demonstrate the test case is effective.

The central critique motivating DCB is that the aggregates of DDD establish strict and rigid consistency
boundaries that may eventually become inappropriate and difficult to refactor. This may be true. We will
investigate later how comparatively easy or difficult it is to refactor sequences of events recorded by
DCB applications and by event-sourced applications.

Another of the arguments motivating DCB is that, `"by definition, the aggregate is the boundary of consistency"
<https://sara.event-thinking.io/2023/04/kill-aggregate-chapter-2-the-aggregate-does-not-fit-the-storytelling.html>`_
and so it is impossible to implement the "course subscriptions" challenge using event-sourced aggregates without
the accidental complexity of awkward tricks.

Whatever the arguments are against aggregates, it is more important that a proposition be interesting than that
it be true. DCB is indeed an interesting novel proposition.

Enrolment with aggregates
-------------------------

The domain model shown below defines :class:`~examples.dcb_enrolment.domainmodel.Course`, an event-sourced aggregate
class for courses that students can join, and :class:`~examples.dcb_enrolment.domainmodel.Student`, an event-sourced
aggregate class for students that may join courses.

.. literalinclude:: ../../../examples/dcb_enrolment/domainmodel.py
    :pyobject: Course

.. literalinclude:: ../../../examples/dcb_enrolment/domainmodel.py
    :pyobject: Student

These aggregate classes are implemented using the concise
:ref:`declarative syntax <Declarative syntax>` supported by this library. These aggregate classes are coded to use string IDs as demonstrated
in :doc:`example 11  </topics/examples/aggregate11>`.


The :class:`~examples.dcb_enrolment.application.EnrolmentWithAggregates` application uses
the :class:`~examples.dcb_enrolment.domainmodel.Course` and :class:`~examples.dcb_enrolment.domainmodel.Student`
aggregate classes to implement the :ref:`enrolment interface <Enrolment interface>`.
The "consistency boundary" for joining a course includes a student and a course.

.. literalinclude:: ../../../examples/dcb_enrolment/application.py
    :pyobject: EnrolmentWithAggregates

This meets the "course subscriptions" challenge with event-sourced aggregates, without tricks and without
accidental complexity. It shows that it is possible and straightforward
to extend the transactional consistency boundary when using event-sourced aggregates to include more than one
aggregate. Indeed, this is a legitimate technique.

At the time of writing, this possibility is not mentioned in the list of
`traditional approaches <https://dcb.events/examples/course-subscriptions/#traditional-approaches>`_ on the dynamic
consistency boundaries website, which lists only three options: eventual consistency, larger aggregate, reservation
pattern.

Test case
---------

The test case below calls :func:`~examples.dcb_enrolment.test_enrolment.EnrolmentTestCase.assert_implementation`
with an instance of :class:`~examples.dcb_enrolment.application.EnrolmentWithAggregates`, configured to use an
in-memory event store and to use PostgreSQL. The third test method shows more explicitly that extending the
transactional consistency boundary when using event-sourced aggregates to include more than one aggregate is
technically sound, by checking that the recorded consistency of the course-student nexus is guarded against
concurrent operations.

.. literalinclude:: ../../../examples/dcb_enrolment/test_application.py
    :pyobject: TestEnrolmentWithAggregates


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
so let's continue by :doc:`implementing the course subscriptions challenge directly with basic DCB objects
</topics/examples/dcb-enrolment-with-basic-objects>`.


Code reference
--------------

.. automodule:: examples.dcb_enrolment.interface
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:
    :special-members: __init__

.. automodule:: examples.dcb_enrolment.test_enrolment
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:
    :special-members: __init__

.. automodule:: examples.dcb_enrolment.domainmodel
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:
    :special-members: __init__

.. automodule:: examples.dcb_enrolment.application
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:
    :special-members: __init__

