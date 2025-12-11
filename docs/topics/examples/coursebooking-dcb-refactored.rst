.. _DCB example 3:

Enduring Objects and Groups
===========================

This example is another attempt at the "course subscriptions" challenge, as seen in the
:doc:`previous example </topics/examples/coursebooking-dcb>`. This time we can show a
higher-level, more refactored style, for `dynamic consistency boundaries <https://dcb.events/>`_,
that encapsulates the lower-level objects and methods described in the `DCB specification <https://dcb.events/specification/>`_
that we used directly in the :doc:`previous example </topics/examples/coursebooking-dcb>`.

The refactored higher-level code shown below introduces the notion "enduring object" which is quite
like "event-sourced aggregate" but with some important differences. And it introduces the notion
"group", which is a collection of many enduring objects that can also make decisions which affect
the whole group. The more general abstraction that has been derived from the previous example is
the notion of a decision-making "perspective". In general, a "perspective" is a selective view of
the past, an apprehension of decisions already made, at the beginning of the process of creating a
new decision. Here, a "perspective" is a projection of a selection of "decision" events already recorded,
that forms a decision model with which a new event can be generated.

Of course, this is just one possible "higher level" style for coding a DCB application.



Supporting abstractions
-----------------------

The abstractions supporting this style of domain model are described briefly below.

The class :class:`~eventsourcing.dcb.domain.Mutates` is the base
class for "decision" events in the domain model. It has "tags" and defines a method
that can mutate an "enduring object" instance using the attributes of the event object.
It does this by calling a convenience method "apply".

.. literalinclude:: ../../../eventsourcing/dcb/domain.py
    :pyobject: Mutates

The class :class:`~eventsourcing.dcb.domain.Initialises` extends
:class:`~eventsourcing.dcb.domain.Mutates` and defines a method
that can construct an "enduring object" instance from an enduring object class,
using its "decision" event attributes.

.. literalinclude:: ../../../eventsourcing/dcb/domain.py
    :pyobject: Initialises

The class :class:`~eventsourcing.dcb.domain.DecoratedFuncCaller` extends
:class:`~eventsourcing.dcb.domain.Mutates` and is used
by the library's :ref:`event decorator <Event decorator>` to "apply" to an
enduring object any "decision" events of the type mentioned in the decorator.

.. literalinclude:: ../../../eventsourcing/dcb/domain.py
    :pyobject: DecoratedFuncCaller

The class :class:`~eventsourcing.dcb.persistence.DCBMapper` is an abstract base class that
defines an interface for converting between :class:`~eventsourcing.dcb.domain.Mutates`
instances and :class:`~eventsourcing.dcb.api.DCBEvent` instances.

.. literalinclude:: ../../../eventsourcing/dcb/persistence.py
    :pyobject: DCBMapper

The class :class:`~eventsourcing.dcb.persistence.DCBEventStore` encapsulates both an instance
of :class:`~eventsourcing.dcb.persistence.DCBMapper` and an instance of
:class:`~eventsourcing.dcb.api.DCBRecorder`, and presents methods
for getting and putting instances of :class:`~eventsourcing.dcb.domain.Mutates`.

A request to get a set of "decision" events will have one or many :class:`~eventsourcing.dcb.domain.Selector`
objects. The selectors will be converted to a :class:`~eventsourcing.dcb.api.DCBQuery` that has one
:class:`~eventsourcing.dcb.api.DCBQueryItem` for each selector. The :class:`~eventsourcing.dcb.api.DCBQuery`
is used to read :class:`~eventsourcing.dcb.api.DCBEvent` instances from the :class:`~eventsourcing.dcb.api.DCBRecorder`.
The :class:`~eventsourcing.dcb.persistence.DCBMapper` is then used to reconstruct :class:`~eventsourcing.dcb.domain.Mutates`
instances from the :class:`~eventsourcing.dcb.api.DCBEvent` instances.

A request to put a sequence of "decision"
events works in the reverse direction, first the mapper is used to convert :class:`~eventsourcing.dcb.domain.Mutates`
instances to :class:`~eventsourcing.dcb.api.DCBEvent` instances, and then the :class:`~eventsourcing.dcb.api.DCBEvent` instances
are appended to the database by the recorder.

.. literalinclude:: ../../../eventsourcing/dcb/persistence.py
    :pyobject: DCBEventStore

The class :class:`~eventsourcing.dcb.domain.Selector` is used to define consistency boundaries
in a domain model, and is therefore used in the method arguments of :class:`~eventsourcing.dcb.persistence.DCBEventStore`.

.. literalinclude:: ../../../eventsourcing/dcb/domain.py
    :pyobject: Selector

The class :class:`~eventsourcing.dcb.application.DCBRepository` has an instance of
:class:`~eventsourcing.dcb.persistence.DCBEventStore`. It defines a method to get one
enduring object for a given continuity ID. It has another method to get a sequence of
enduring objects for a given sequence of continuity IDs. And it has another method to construct
a particular type of group of enduring objects, given a group class and a sequence of continuity IDs.
It also has a method to "save" enduring objects and groups, or indeed any perspective, which collects
new events and uses their "consistency boundary" and "last known position" to append the new events
with the DCB optimistic concurrency control logic referred to as the "append condition".

.. literalinclude:: ../../../eventsourcing/dcb/application.py
    :pyobject: DCBRepository

The class :class:`~eventsourcing.dcb.domain.EnduringObject` is a base class for enduring objects, which can have
command methods that trigger "decision" events, and which define a projection of a sequence of "decision" events
into a current state. Subclasses are capable of creating instances when called, by triggering an "initial decision"
event, that is used to actually construct an enduring object instance, and which is then appended to an internal
list of new events on that instance. It provides a default implementation of a method to create unique continuity IDs.
It also has a "trigger event" method that can be used to generate and apply subsequent "decision" events. It defines
a default consistency boundary that is simply a :class:`~eventsourcing.dcb.domain.Selector` that has the continuity ID
of an enduring object as its only tag.

.. literalinclude:: ../../../eventsourcing/dcb/domain.py
    :pyobject: EnduringObject

The class :class:`~eventsourcing.dcb.domain.Group` is a base class for cross-cutting decision-making groups of
enduring objects. It defines a default consistency boundary that is the union of the consistency boundaries of the
enduring objects in the group. It also has a method to trigger a new "decision" event. New "decision" events are
applied to all the enduring objects in the group, and then appended to an internal list of new events.

.. literalinclude:: ../../../eventsourcing/dcb/domain.py
    :pyobject: Group

The class :class:`~eventsourcing.dcb.domain.Perspective` is the common base class for
:class:`~eventsourcing.dcb.domain.EnduringObject` and :class:`~eventsourcing.dcb.domain.Group`
and defines an interface from which consistency boundaries, last known positions, and new "decision" events
can be collected.

.. literalinclude:: ../../../eventsourcing/dcb/domain.py
    :pyobject: Perspective

The choice of the term "perspective" for this class, and the usage of the term "enduring object" here, follow from
the modern process philosophy of Alfred North Whitehead.

.. pull-quote::

    *"The 'settlement' which an actual entity 'finds' is its datum. It is to be conceived as a limited perspective
    of the 'settled' world provided by the eternal objects concerned. This datum is 'decided' by the settled world.
    It is 'prehended' by the new superseding entity. The datum is the objective content of the experience. The
    decision, providing the datum, is a transference of self-limited appetition; the settled world provides the
    'real potentiality' that its many actualities be felt compatibly; and the new concrescence starts from this
    datum. The perspective is provided by the elimination of incompatibilities. The final stage, the 'decision'
    is how the actual entity, having attained its individual 'satisfaction' thereby adds a determinate condition
    to the settlement for the future beyond itself. Thus the 'datum' is the 'decision received' and the 'decision'
    is the 'decision transmitted'. Between these two decisions, received and transmitted, there lie the two stages,
    'process' and 'satisfaction'."*

    *"A nexus enjoys 'personal order' when (a) it is a 'society' and (b) when
    the genetic relatedness of its members orders these members 'serially'.
    By this 'serial ordering' arising from the genetic relatedness, it is meant
    that any member of the nexus — excluding the first and the last, if there be
    such — constitutes a 'cut' in the nexus, so that (a) this member inherits
    from all members on one side of the cut, and from no members on the
    other side of the cut, and (b) if A and B are two members of the nexus
    and B inherits from A, then the side of B's cut, inheriting from B, forms
    part of the side of A's cut, inheriting from A, and the side of A's cut from
    which A inherits forms part of the side of B's cut from which B inherits.
    Thus the nexus forms a single line of inheritance of its defining characteristic.
    Such a nexus is called an 'enduring object'."*

The class :class:`~eventsourcing.dcb.msgspecstruct.Decision` extends
:class:`~eventsourcing.dcb.domain.Mutates` and uses :class:`Struct`
from the :data:`msgspec` package to define a base class for concrete "decision" events
that can define instance attributes using type annotations, and that can be serialised and
deserialised very quickly.

.. literalinclude:: ../../../eventsourcing/dcb/msgspecstruct.py
    :pyobject: Decision

The class :class:`~eventsourcing.dcb.msgspecstruct.InitialDecision` extends
:class:`~examples.coursebookingdcbrefactored.application.Decision` and
:class:`~eventsourcing.dcb.domain.Initialises` to define a base class
for concrete "initial decision" events that can define object attributes using type annotations.

.. literalinclude:: ../../../eventsourcing/dcb/msgspecstruct.py
    :pyobject: InitialDecision

The class :class:`~eventsourcing.dcb.msgspecstruct.MsgspecStructMapper` implements
the :class:`~eventsourcing.dcb.persistence.DCBMapper` interface so that :class:`~examples.coursebookingdcbrefactored.application.Decision`
instances can be converted to :class:`~eventsourcing.dcb.api.DCBEvent` instances, and so that
:class:`~eventsourcing.dcb.api.DCBEvent` instances can be converted back to a copy of the original
:class:`~examples.coursebookingdcbrefactored.application.Decision` instance, both using the super
fast and compact `msgpack <https://msgpack.org>`_ format.

.. literalinclude:: ../../../eventsourcing/dcb/msgspecstruct.py
    :pyobject: MsgspecStructMapper

Application
-----------

The refactored "enrolment" application class :class:`~examples.coursebookingdcbrefactored.application.EnrolmentWithDCBRefactored`
shown below implements :class:`~examples.coursebooking.interface.EnrolmentInterface`. Unlike the previous example,
its methods are all very short three-line blocks, which mostly initialise or reconstruct a "perspective" (line 1),
make a new decision (line 2), and then append new events to the database (line 3). Because this style so easy to code,
we added more methods just for fun!

This version looks a lot like the application that uses event-sourced aggregates in the
:doc:`first example </topics/examples/coursebooking>`.

One interesting difference is the repository has methods not only to "get" one enduring object, but also to
get many enduring objects in one request, and also to get a "group" of enduring objects of a particular type.
Can you find examples of calling these three repository methods in the code below?

.. literalinclude:: ../../../examples/coursebookingdcbrefactored/application.py
    :pyobject: EnrolmentWithDCBRefactored

Domain model
------------

The application uses a domain model that defines :class:`~examples.coursebookingdcbrefactored.application.Student`
and :class:`~examples.coursebookingdcbrefactored.application.Course` as "enduring objects".

The base class :class:`~eventsourcing.dcb.domain.EnduringObject` works in a similar way to an event-sourced aggregate.
Each instance has a unique continuity ID. Each can have command methods that trigger events. Their command methods
can be decorated with the library's :ref:`event decorator <Event decorator>`. Calling such commands generates new events.

The main difference between "event-sourced aggregates" and "enduring objects" in this code is that "enduring objects"
generate events that do not have an originator ID or a version number, but instead have a list of tags. The events
generated by an enduring object are simply tagged with the enduring object's continuity ID. Recorded events that
pertain to an enduring object will be selected with its continuity ID as a tag.

.. literalinclude:: ../../../examples/coursebookingdcbrefactored/application.py
    :pyobject: Student

.. literalinclude:: ../../../examples/coursebookingdcbrefactored/application.py
    :pyobject: Course


This domain model for "course subscriptions" also defines a "group" called :class:`~examples.coursebookingdcbrefactored.application.StudentAndCourse`.
It is derived from the base class :class:`~eventsourcing.dcb.domain.Group`.
A group can trigger events. For example, the :class:`~examples.coursebookingdcbrefactored.application.StudentAndCourse`
group can trigger two events, :class:`~examples.coursebookingdcbrefactored.application.StudentJoinedCourse` and
:class:`~examples.coursebookingdcbrefactored.application.StudentLeftCourse`.

A "group" is constructed with many enduring objects and can make decisions, each of which which can
simultaneously affect all of the enduring objects in the group. This is the "one fact" magic
of DCB.

Events triggered by a group will each be tagged with all the continuity IDs of the enduring objects in the group. Such
events will immediately be applied to all the enduring objects, just like an event triggered by an event-sourced
aggregate or an enduring object will be applied immediately to its current state.

Because of the multi-tagging, such events will also be selected and applied whenever one of the enduring objects
is subsequently reconstructed. That is why :class:`~examples.coursebookingdcbrefactored.application.Student` and
:class:`~examples.coursebookingdcbrefactored.application.Course` have non-command "underscore" methods to register how
such cross-cutting events will be projected into their current state.

.. literalinclude:: ../../../examples/coursebookingdcbrefactored/application.py
    :pyobject: StudentAndCourse

.. literalinclude:: ../../../examples/coursebookingdcbrefactored/application.py
    :pyobject: StudentJoinedCourse

.. literalinclude:: ../../../examples/coursebookingdcbrefactored/application.py
    :pyobject: StudentLeftCourse

Again, all of this is just one way of styling a slightly higher-level abstraction over the objects and methods described
in the DCB specification. But we think it expresses the concerns in the "course subscriptions" challenge clearly and
concisely.



Test case
---------

The test case is the same as the :doc:`first example </topics/examples/coursebooking>`, but executed
with the :class:`~examples.coursebookingdcbrefactored.application.EnrolmentWithDCBRefactored` class above.
It runs once with the  :class:`~eventsourcing.dcb.popo.InMemoryDCBRecorder` introduced in the previous
example, and once with the :class:`~eventsourcing.dcb.postgres_tt.PostgresDCBRecorderTT` introduced above.

.. literalinclude:: ../../../examples/coursebookingdcbrefactored/test_application.py
    :pyobject: TestEnrolmentWithDCBRefactored

It also has some extra steps to cover the extra methods that were added to make further use of the more
declarative syntax for DCB, such as a student leaving a course, changes of name of students and courses,
and changes to the number of "places" a course has and the "max courses" for student.

The extra steps also show the command methods of enduring objects in a group can be executed. New events
from the group and from its enduring objects are collected when a group is saved.

The extra steps also show that concurrent changes to enduring objects conflict with the student-course
group, both for relevant events (such as changes to the 'max_courses' and 'places' numbers which are
relevant when a student joins a course) but also for irrelevant events (such as changed to a student's name).
It would be possible to reconstruct enduring objects and groups with more restricted consistency boundaries,
but then attributes that would be updated from events that are not included will have stale values. This
aspect is remedied by using the "vertical slices" style that is shown in the
:doc:`next example </topics/examples/coursebooking-dcb-slices>`.



We think the refactored style looks quite nice.

This library supports DCB by the abstractions for domain models and applications discussed above. If you want to use the msgspec "decision" event classes and mapper, then just
copy the example code into your project. If you prefer to use Pydantic or dataclasses or attrs or something
else, then please just craft your own concrete "decision" event classes and mapper.


Code reference
--------------

.. automodule:: examples.coursebookingdcbrefactored.application
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:
    :special-members: __init__

