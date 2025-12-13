.. _DCB example 3:

DCB 3 - Enduring Objects and Groups
===================================


Here we implement the :doc:`course subscriptions challenge </topics/examples/dcb-enrolment-introduction>`
with a higher-level style for DCB that uses :ref:`enduring objects <Enduring object>` and a :ref:`group <Group>`.

Domain model
------------

The domain model defines :class:`~examples.dcb_enrolment_with_enduring_objects.application.Student`
and :class:`~examples.dcb_enrolment_with_enduring_objects.application.Course` as :ref:`enduring objects <Enduring object>`.

The :class:`~examples.dcb_enrolment_with_enduring_objects.application.Student` has an ID, a name, and
maximum number of courses.

.. literalinclude:: ../../../examples/dcb_enrolment_with_enduring_objects/application.py
    :pyobject: Student

The :class:`~examples.dcb_enrolment_with_enduring_objects.application.Course` has an ID, a name, and
number of places for students.

.. literalinclude:: ../../../examples/dcb_enrolment_with_enduring_objects/application.py
    :pyobject: Course

Both classes include the event The :class:`~examples.dcb_enrolment_with_enduring_objects.application.StudentJoinedCourse`
in their projection, but neither has a command method for doing so.

The cross-cutting concern of a student joining and leaving a course is implemented with the :ref:`group <Group>`
:class:`~examples.dcb_enrolment_with_enduring_objects.application.StudentAndCourse`.

.. literalinclude:: ../../../examples/dcb_enrolment_with_enduring_objects/application.py
    :pyobject: StudentAndCourse

.. literalinclude:: ../../../examples/dcb_enrolment_with_enduring_objects/application.py
    :pyobject: StudentJoinedCourse

.. literalinclude:: ../../../examples/dcb_enrolment_with_enduring_objects/application.py
    :pyobject: StudentLeftCourse


Application
-----------

The application class :class:`~examples.dcb_enrolment_with_enduring_objects.application.EnrolmentWithEnduringObjects`
implements the :ref:`enrolment interface <Enrolment interface>`. Unlike the previous example,
its methods are all very short three-line blocks, which mostly initialise or reconstruct a "perspective" (line 1),
make a new decision (line 2), and then append new events to the database (line 3). Because this style so easy to code,
we added more methods just for fun!

This version looks a lot like the application that uses event-sourced aggregates in the
:doc:`first example </topics/examples/dcb-enrolment-introduction>`.

One interesting difference is the :ref:`repository <DCB Repository>` has methods not only to get one enduring object,
but also to get many enduring objects in one request, and to get a "group" of enduring objects of a particular type.

.. literalinclude:: ../../../examples/dcb_enrolment_with_enduring_objects/application.py
    :pyobject: EnrolmentWithEnduringObjects

Test case
---------

The :ref:`enrolment test case <Enrolment test case>` is extended for
:class:`~examples.dcb_enrolment_with_basic_objects.application.EnrolmentWithEnduringObjects`.

It has some extra steps to cover the extra methods that we have implemented.

.. literalinclude:: ../../../examples/dcb_enrolment_with_enduring_objects/test_application.py
    :pyobject: TestEnrolmentWithEnduringObjects

It has some extra steps to cover the extra methods that were added to make further use of the more
declarative syntax for DCB, such as a student leaving a course, changes of name of students and courses,
and changes to the number of "places" a course has and the "max courses" for student.

The extra steps also show the command methods of enduring objects in a group can be executed. New events
from the group and from its enduring objects are collected when a group is saved.

The extra steps also show that concurrent changes to enduring objects conflict with the student-course
group, both for relevant events (such as changes to the 'max_courses' and 'places' numbers which are
relevant when a student joins a course) but also for irrelevant events (such as changed to a student's name).
It would be possible to reconstruct enduring objects and groups with more restricted consistency boundaries,
but then attributes that would be updated from events that are not included will have stale values.


Discussion
----------

This is just one way of styling a slightly higher-level abstraction over the objects and methods described
in the DCB specification.

Overall, we think it expresses the concerns in the "course subscriptions" challenge clearly and
concisely. The conceptual overhead is relatively low. However, the full flexibility of DCB is not
utilised by this approach, since each consistency boundary for an enduring object includes its full
sequence of events. This means that commands which in fact are not contentious, such as changing the
name of a student whilst the student is being enrolled on a course, could conflict if undertaken
concurrently, which is unnecessary. This aspect is remedied by using the "vertical slices"
style that is shown in the :doc:`next example </topics/examples/dcb-enrolment-with-vertical-slices>`,
perhaps at the cost of increased conceptual overhead.

Code reference
--------------

.. automodule:: examples.dcb_enrolment_with_enduring_objects.application
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:
    :special-members: __init__

