.. _DCB example 4:

DCB 4 - Vertical Slices
=======================

This example is another attempt at the "course subscriptions" challenge. This time we show another
variation of the higher-level, more refactored style that we used in the
:doc:`previous example </topics/examples/dcb-enrolment-with-enduring-objects>`.

This implementation introduces the notion "slice" from the "vertical slices"
style advocated by the event modelling community.

Each slice defines a tight consistency boundary that is specific to its use case. Events for a slice are
selected according to its consistency boundary, and projected into a "current state" for a slice according
to its own projector function. This produces a "current state" which is used sometimes as a "decision model"
for slices that generate new events in application command methods, and in other cases to support returning
values from application query methods.

Events
------

The "decision" events that the slices depend on are shown below. They all derive from
the :ref:`decision <DCB Decision>` class.

.. literalinclude:: ../../../examples/dcb_enrolment_with_vertical_slices/application.py
    :pyobject: StudentJoinedCourse

.. literalinclude:: ../../../examples/dcb_enrolment_with_vertical_slices/application.py
    :pyobject: StudentLeftCourse

.. literalinclude:: ../../../examples/dcb_enrolment_with_vertical_slices/application.py
    :pyobject: StudentRegistered

.. literalinclude:: ../../../examples/dcb_enrolment_with_vertical_slices/application.py
    :pyobject: StudentNameUpdated

.. literalinclude:: ../../../examples/dcb_enrolment_with_vertical_slices/application.py
    :pyobject: StudentMaxCoursesUpdated

.. literalinclude:: ../../../examples/dcb_enrolment_with_vertical_slices/application.py
    :pyobject: CourseRegistered

.. literalinclude:: ../../../examples/dcb_enrolment_with_vertical_slices/application.py
    :pyobject: CourseNameUpdated

.. literalinclude:: ../../../examples/dcb_enrolment_with_vertical_slices/application.py
    :pyobject: CoursePlacesUpdated

Slices
------

Each slice shown below derives from the base class :class:`~eventsourcing.dcb.domain.Slice`.

The slices shown below are entirely independent of each other. They depend only on the "decision" event classes
that are relevant to their use case. The big advantage of this style is that because slices define tight consistency
boundaries according to their requirements, they will select only the events they actually require. And it naturally
arises that there will be much less accidental overlap in the consistency boundaries between use cases. This means,
in theory, there will be less contention between concurrent operations involving different use cases with the same tags.
But more importantly, the decision models and the consistency boundaries are well-matched to each other and to the use
case. That's why this is a great style.


.. literalinclude:: ../../../examples/dcb_enrolment_with_vertical_slices/application.py
    :pyobject: RegisterStudent

.. literalinclude:: ../../../examples/dcb_enrolment_with_vertical_slices/application.py
    :pyobject: UpdateStudentName

.. literalinclude:: ../../../examples/dcb_enrolment_with_vertical_slices/application.py
    :pyobject: UpdateMaxCourses

.. literalinclude:: ../../../examples/dcb_enrolment_with_vertical_slices/application.py
    :pyobject: RegisterCourse

.. literalinclude:: ../../../examples/dcb_enrolment_with_vertical_slices/application.py
    :pyobject: UpdateCourseName

.. literalinclude:: ../../../examples/dcb_enrolment_with_vertical_slices/application.py
    :pyobject: UpdatePlaces

.. literalinclude:: ../../../examples/dcb_enrolment_with_vertical_slices/application.py
    :pyobject: StudentJoinsCourse

.. literalinclude:: ../../../examples/dcb_enrolment_with_vertical_slices/application.py
    :pyobject: StudentLeavesCourse

.. literalinclude:: ../../../examples/dcb_enrolment_with_vertical_slices/application.py
    :pyobject: StudentsIDs

.. literalinclude:: ../../../examples/dcb_enrolment_with_vertical_slices/application.py
    :pyobject: StudentNames

.. literalinclude:: ../../../examples/dcb_enrolment_with_vertical_slices/application.py
    :pyobject: CourseIDs

.. literalinclude:: ../../../examples/dcb_enrolment_with_vertical_slices/application.py
    :pyobject: CourseNames

.. literalinclude:: ../../../examples/dcb_enrolment_with_vertical_slices/application.py
    :pyobject: Student

.. literalinclude:: ../../../examples/dcb_enrolment_with_vertical_slices/application.py
    :pyobject: Course

Application
-----------

The nice thing about this implementation is that the application command methods have all become straightforward
one-liners that simply allow the domain model defined by the slices to enjoy the persistence infrastructure provided
by the application. This happens naturally by pushing into the slices all responsibilities for selecting events,
for projecting events into a decision model, and for generating new events, keeping
their differences encapsulated behind a standard interface.

.. literalinclude:: ../../../examples/dcb_enrolment_with_vertical_slices/application.py
    :pyobject: EnrolmentWithVerticalSlices


Test case
---------

The :ref:`enrolment test case <Enrolment test case>` is extended to check
:class:`~examples.dcb_enrolment_with_basic_objects.application.EnrolmentWithVerticalSlices`.

It has some extra steps to cover the extra methods that we have implemented, such as a student leaving a course,
changes of name, changes to the number of places on a course and the "max courses" for student.
The extra steps also show, a little bit, the non-conflicting nature of different slices.

.. literalinclude:: ../../../examples/dcb_enrolment_with_vertical_slices/test_application.py
    :pyobject: TestEnrolmentWithVerticalSlices


Discussion
----------

It must be said, that this is great style. We think "slices" and "dynamic consistency
boundaries" really go very well together, and we hope you agree.

To be fair, as we saw with the :doc:`shopping cart </topics/examples/shop-vertical>` example, "vertical slices"
make the code altogether slightly repetitive, relatively verbose, and relatively complicated. Whilst some may
enjoy the absolute separation between use cases, others may find "vertical slices" harder to reason about than
event-sourced aggregates and the "enduring objects" that were discussed in the previous example. Certainly,
unlike the event-sourced aggregates, these slices do not all fit on one screen. The "decision" events that
naturally fall into sequences under one tag are not coherently encapsulated in a single entity, and there
are many different consistency boundaries. For these reasons, there will tend to be a greater need for careful
thought, and longer tests, without which this style seems to invite a greater likelihood of unseen programming
errors.

When considering contention, we must remember that compared with, for example, event-sourced aggregates
which use a simpler and therefore faster persistence model, DCB read and append operations are inherently
more complex and therefore slower. As a result, although with "vertical slices" we can more easily code
for tighter consistency boundaries, due to the slower operations of DCB, there will, in theory, be more
risk of roughly contemporary operations actually happening concurrently, causing contention where contention
would not have occurred. But of course, there will be no conflict between operations involving sequences for
different continuity IDs, in DCB, with or without "slices", and with or without event-sourced aggregates,
and so this is a relatively marginal consideration in most cases.

Whatever the relative merits, above all, we value having and supporting different styles and persistence
models for event sourcing. And DCB with "vertical slices" is indeed a very commendable style.


Code reference
--------------

.. automodule:: examples.dcb_enrolment_with_vertical_slices.application
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:
    :special-members: __init__

