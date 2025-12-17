============================================================
:mod:`~eventsourcing.dcb` --- Dynamic consistency boundaries
============================================================

From version 9.5, this library supports Dynamic Consistency Boundaries (DCB) by providing:

* an :ref:`implementation <DCB Objects>` in Python of the basic objects defined in the `specification <https://dcb.events/specification/>`_
* a range of :ref:`event stores <DCB recorders>` that work in memory, with PostgreSQL, and with UmaDB
* some :ref:`higher-level abstractions <Higher-level abstractions>` to make working with DCB easier
* support in the :doc:`projections module </topics/projection>` for eventually-consistent materialized views

.. _Introduction to DCB:

Introduction to DCB
===================

Dynamic Consistency Boundaries is a significant variant of event sourcing presented in a
`humorously provocative way <https://sara.event-thinking.io/2023/04/kill-aggregate-chapter-1-I-am-here-to-kill-the-aggregate.html>`_
as "killing the aggregate".

The DCB Specification
---------------------

A `novel scheme <https://dcb.events/specification/>`_ has been proposed that uses a single sequence of
events, an :ref:`application sequence <Overview>` in the terminology of this library.

Events
~~~~~~

Each event in DCB has one "type" string, some "data", and any number of "tag" strings.
Recorded events also have an assigned "position" in the sequence, and for this reason are referred to as
"sequenced events". These objects correspond to the :ref:`stored event <Stored event objects>` and
:ref:`notification <Notification objects>` objects previously defined in this library.

Reading
~~~~~~~

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

Writing
~~~~~~~

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
"last known position" at the time of reading can be used as the append condition position.

The command method's query, that is used both when reading a writing, therefore defines the "dynamic consistency
boundary" for the command.

Discussion
----------

The multi-dimensional possibilities offered by combining a set of different query items is impressive. However,
this presents a technical challenge when implementing support for DCB applications. Firstly, the selections of
events have to be correct for all possible sets of query items. But then also, it will be a technical challenge
to achieve performance times for DCB applications that is comparable to that enjoyed by "traditional" event-sourced
aggregates.

A sustained effort has been made here to implement support for DCB is a way that is both correct and performant. At
first, an attempt was made to use GIN indexes in PostgreSQL, with both array operators and then with text vectors and
then with full text search techniques. Many others have tried this too, in different ways. It is commonly experienced
to be slow with any significant volume of recorded events. In consequence, an alternative implementation in PostgreSQL
was developed that uses B+trees with a separate table for tags. This was much faster, especially when coded with common
table expressions. Finally, the idea of using B+ trees with CTEs in PostgreSQL was distilled into a specialist DCB event
store written in Rust, now called `UmaDB <https://umadb.io>`_.

Furthermore, we have searched for a high-level abstraction with which domain logic can be more easily expressed. Ideas
developed in this library for serialisation, mapping, and declarative syntax have been applied, along with ideas for
implementing business logic with "vertical slices".

.. _DCB Objects:

DCB Objects
===========

Here we present an implementation in Python of the basic objects for DCB that are
described in the specification and discussed in the :ref:`introduction <Introduction to DCB>`
above.

See :doc:`this example </topics/examples/dcb-enrolment-with-basic-objects>` of
using the basic DCB objects to meet the course subscriptions challenge.

.. _DCB Query Item:

DCB Query Item
--------------

A :class:`~eventsourcing.dcb.api.DCBQueryItem` defines a criterion for matching events.
A query item will match an event if: one of its types matches the event's type or the
query item's types attribute is empty; and if all of its tags match one of the event's tags
or the query item's tags attribute is empty.

.. code-block:: python

    from eventsourcing.dcb.api import DCBQueryItem

    student_query_item = DCBQueryItem(
        types=["StudentRegistered"],
        tags=["student:123"],
    )


.. _DCB Query:

DCB Query
---------

A :class:`~eventsourcing.dcb.api.DCBQuery` defines criteria for :ref:`selecting <DCB Recorders>` events in an event store.
An :ref:`event <DCB Event>` is selected if it is matched by any :ref:`query item <DCB Query Item>` included in ``items`` attribute,
or if the ``items`` attribute is empty.

.. code-block:: python

    from eventsourcing.dcb.api import DCBQuery

    student_query = DCBQuery(
        items=[student_query_item],
    )

.. _DCB Event:

DCB Event
---------

A :class:`~eventsourcing.dcb.api.DCBEvent` represents a settled collection of facts to be appended, or
that has already been recorded, in an :ref:`event store <DCB Recorders>`.

.. code-block:: python

    from eventsourcing.dcb.api import DCBEvent

    student_registered = DCBEvent(
        type="StudentRegistered",
        data=b'{"student_id": "student:123", "name": "Sara", "max_courses": 5}',
        tags=["student:123"],
    )

    course_registered = DCBEvent(
        type="CourseRegistered",
        data=b'{"course_id": "course:456", "name": "History", "max_students": 30}',
        tags=["course:456"],
    )


.. _DCB Sequenced Event:

DCB Sequenced Event
-------------------

A :class:`~eventsourcing.dcb.api.DCBSequencedEvent` represents a recorded :ref:`event <DCB Event>` along
with its assigned sequence number.

.. code-block:: python

    from eventsourcing.dcb.api import DCBSequencedEvent

    DCBSequencedEvent(
        event=student_registered,
        position=56316,
    )

    DCBSequencedEvent(
        event=course_registered,
        position=56317,
    )


.. _DCB Append Condition:

DCB Append Condition
--------------------

A :class:`~eventsourcing.dcb.api.DCBAppendCondition` causes an :ref:`append <DCB Recorders>` request to fail if events
match the :ref:`query <DCB Query>` value of its ``fail_if_events_match`` attribute, optionally
after a sequence number.

.. code-block:: python

    from eventsourcing.dcb.api import DCBAppendCondition

    append_condition = DCBAppendCondition(
        fail_if_events_match=student_query,
        after=None,
    )


.. _DCB Recorders:

DCB Recorders
=============

The term "recorder" here corresponds to the notion "event store" in the DCB
specification, and refers to the notion of dealing with records. Following the
terminology in this library, the term "recorder" is used for dealing with domain
events that have been serialised into a common format, and the term "event store"
is used both for a higher-level objects that deal with domain event objects of
different types, and for specialist event store databases.

Abstract base class
-------------------

The abstract base class :class:`~eventsourcing.dcb.api.DCBRecorder` defines the
:func:`~eventsourcing.dcb.api.DCBRecorder.read` and :func:`~eventsourcing.dcb.api.DCBRecorder.append`
method signatures described in the DCB specification for an "event store". These methods depend on
the :ref:`DCB Objects` described above.

.. literalinclude:: ../../eventsourcing/dcb/api.py
    :pyobject: DCBRecorder

We have made two enhancements that go beyond the DCB specification.

The first enhancement is the standard idea to return :class:`int` from the :func:`~eventsourcing.dcb.api.DCBRecorder.append`
method. This value represents the position of the last appended event. By returning this position, systems
implemented with CQRS that transition from a "write" view to an eventually-consistent "read" view can
wait for new events to be processed, by forwarding this value in the read request, avoiding the stale
read model problem.

The second enhancement is to support subscriptions, with the :func:`~eventsourcing.dcb.api.DCBRecorder.subscribe`
method, so that readers can continue receiving newly recorded events.

Read response
-------------

The :func:`~eventsourcing.dcb.api.DCBRecorder.read` method returns a :class:`~eventsourcing.dcb.api.DCBReadResponse`,
which is a Python iterator that returns :class:`~eventsourcing.dcb.api.DCBSequencedEvent` objects.
It has a :data:`~eventsourcing.dcb.api.DCBReadResponse.head` property that allows a reader to obtain a
"last known position" that corresponds to the last recorded event in the database at the time of reading,
rather than the sequence number of the last event it receives. This gives a better value for subsequent
append conditions.

Subscription
------------

The :func:`~eventsourcing.dcb.api.DCBRecorder.subscribe` method returns a :class:`~eventsourcing.dcb.api.DCBSubscription`
object, which is a Python iterator that returns :class:`~eventsourcing.dcb.api.DCBSequencedEvent` objects. It
can be used as a context manager.

The following sections describe various implementations of the :class:`~eventsourcing.dcb.api.DCBRecorder` interface.

.. _In-memory DCB recorder:

In-memory DCB recorder
----------------------

The :class:`~eventsourcing.dcb.popo.InMemoryDCBRecorder` class implements the :class:`~eventsourcing.dcb.api.DCBRecorder`
interface using only Python objects.

.. code-block:: python

    from eventsourcing.dcb.popo import InMemoryDCBRecorder

    in_memory_recorder = InMemoryDCBRecorder()

    # Conditionally append new events.
    in_memory_recorder.append(
        events=[student_registered],
        condition=append_condition,
    )

    # Read previously appended events.
    student_events = in_memory_recorder.read(
        query=student_query,
    )

It can be used by a DCB application by setting the ``PERSISTENCE_MODULE`` environment variable to ``"eventsourcing.dcb.popo"``.

DCB events are stored in memory, and "deep copied" when appending and when reading to avoid any corruption
of sequenced events. If you click through to the source code, you can see the DCB query logic for selecting
events, and the append condition logic that is implemented in the append method. This is extremely fast for
relatively low volumes of events, and is ideal for use in unit test suites.

.. _Postgres DCB recorder:

Postgres DCB recorder
---------------------

The :class:`~eventsourcing.dcb.postgres_tt.PostgresDCBRecorderTT` class implements
:class:`~eventsourcing.dcb.api.DCBRecorder` in PostgreSQL using the following approach.

It can be used by a DCB application by setting the ``PERSISTENCE_MODULE`` environment
variable to ``"eventsourcing.dcb.postgres_tt"``, along with other settings such as the database name
and password (see examples).

This is our third attempt to implement the complex DCB query logic in PostgreSQL. The first attempt used
array columns and array operators. The second attempt used text search. Both of these first two attempts
gave poor results. The third attempt, explained below, gives much better results.

The general idea is that tags tend to follow from individual enduring objects in the real world, whereas
event type strings follow from software object classes in a domain model. Therefore tags tend to have
high cardinality, whereas type strings tend to have low cardinality. Therefore tags tend to be highly
selective in queries, whereas type strings do not. Mixing these up in an SQL select statement causes
the PostgreSQL query planner to find sub-optimal solutions.

This implementation uses an secondary table of tags indexed with a B-tree. Queries select tags first, and then
filter by position and type. The sequence positions on the main table are also indexed with a B-tree that
"covers" the type column. In this way, recorded events can be selected by tag, filtered by type, ordered and limited,
using only B-tree indexes, without touching the main table of recorded events.

Conditional append operations use separate multi-clause "fail condition" and "unconditional append" CTE statements.
Having two separate statements in a PL/pgSQL function means each can be planned separately, whilst conditional append
operations can be performed efficiently with one client-server round-trip. The function parameters include lists
of DCB query items and DCB events, defined as composite arrays of custom types. A multi-clause CTE statement is also
used to select events for read operations. These functions are executed as prepared statements.

Logging execution times directly from the database shows that the database typically executes conditional appends
in 100-200 μs with millions of recorded events.

See the :doc:`speedrun example for a comparative report and analysis of the performance </topics/examples/dcb-enrolment-speedrun>`.

.. _UmaDB DCB recorder:

UmaDB DCB recorder
------------------

UmaDB is a `specialist event store for DCB <https://umadb.io>`_. The `Python package <https://pypi.org/project/eventsourcing-umadb/>`_
``eventsourcing_umadb`` implements :class:`~eventsourcing.dcb.api.DCBRecorder` by adapting the `Python client for UmaDB <https://pypi.org/project/umadb/>`_.

It can be used by a DCB application by setting the ``PERSISTENCE_MODULE`` environment variable to ``"eventsourcing_umadb"``.

UmaDB uses the same idea as the :ref:`Postgres DCB recorder` of filtering first by tags.
UmaDB is written in Rust and follows the CoW MVCC design of `LMDB <https://en.wikipedia.org/wiki/Lightning_Memory-Mapped_Database>`_.

See the :doc:`speedrun example for a comparative report and analysis of the performance </topics/examples/dcb-enrolment-speedrun>`.

.. _Higher-level abstractions:

Higher-level Abstractions
=========================

The following sections describe higher-level abstractions for event sourcing with DCB.

The refactored higher-level code shown below introduces the notion "enduring object" which is quite
like "event-sourced aggregate" but with some important differences, the notion
"group", which is a collection of many enduring objects that can also make decisions which affect
the whole group, and the notion "slice" which can be used with "vertical slice architecture".

The more general abstraction that has been derived is the notion of a decision-making
"perspective". In general, a "perspective" is a selective view of the past, an apprehension of decisions
already made, at the beginning of the process of creating a new decision. Here, a "perspective" is a
selection of decisions already recorded, that forms the "datum" for a decision model which generates new
decision.

In order to reach towards a coherent scheme, some of the names have been borrowed from
the highly relevant event-oriented modern process philosophy of Alfred North Whitehead.

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

The abstractions supporting the higher-level styles of domain modelling with DCB are described briefly below with short examples.


.. _DCB Decision:

Decision
--------

The :class:`~eventsourcing.dcb.domain.Decision` class is defined as the root of
the decision class hierarchy in domain models that uses DCB.

It represents the general notion of giving form to the settled production of new facts
in a domain model. Concrete subclasses will each define a name and a collection of attributes,
and will be somehow serializable and deserializable. Abstract subclasses may involve some kind
of declarative syntax that supports automatic serialisation, such as we see with Pydantic and
MessagePack.

The examples below define decision types as Python data classes.

.. code-block:: python

    from dataclasses import dataclass
    from eventsourcing.dcb.domain import Decision


    @dataclass
    class StudentRegistered(Decision):
        student_id: str
        name: str
        max_courses: int


    @dataclass
    class CourseRegistered(Decision):
        course_id: str
        name: str
        max_students: int


    student_registered = StudentRegistered(
        student_id="student:123",
        name="Sara",
        max_courses=5,
    )

    course_registered = CourseRegistered(
        course_id="course:456",
        name="History",
        max_students=30,
    )


Additionally, the class :class:`~eventsourcing.dcb.domain.InitialDecision` can be used to represent the first
decision in a modelled set of decisions that have serial order (a sequence). It extends :class:`~eventsourcing.dcb.domain.Decision`
with an "originator topic" type hint that may be implemented to represent the type thing to which the sequence
belongs. All the members of such a sequence of decisions are likely each to be tagged with a common tag,
and perhaps also other tags for cross-cutting decisions or other classifications. The common tag in this case
is likely to represent the continuity ID of the thing to which the whole sequence belongs.

.. _DCB TDecision:

TDecision
---------

The type variable :type:`~eventsourcing.dcb.domain.TDecision` represents
any subclass of :class:`~eventsourcing.dcb.domain.Decision`. It will be used
as a type parameter to define generic types that can be specialized to work
with one kind of decision or another.

.. _DCB Tagged:

Tagged
------

The generic class :class:`~eventsourcing.dcb.domain.Tagged` encapsulates a
:class:`~eventsourcing.dcb.domain.Decision`, along with some tag strings.
It corresponds to the "typed and tagged" lower-level :ref:`DCB event <DCB Event>` type.

.. literalinclude:: ../../eventsourcing/dcb/domain.py
    :pyobject: Tagged


.. code-block:: python

    from eventsourcing.dcb.domain import Tagged

    tagged_decision = Tagged[StudentRegistered](
        tags=["student:123"],
        decision=student_registered,
    )


.. _DCB Mapper:

Mapper
------

The class :class:`~eventsourcing.dcb.persistence.DCBMapper` is an abstract base class that
defines an interface for converting between the higher-level :class:`~eventsourcing.dcb.domain.Decision`
instances and the lower-level :class:`~eventsourcing.dcb.api.DCBEvent` instances.

.. literalinclude:: ../../eventsourcing/dcb/persistence.py
    :pyobject: DCBMapper

Concrete subclasses will implement or invoke some kind of serialization and deserialization functionality,
for example by using JSON, Pydantic, MessagePack, or Protobuf.

.. code-block:: python

    import json

    class JSONMapper(DCBMapper[Decision]):
        def __init__(self, registered_types: list[type[Decision]]) -> None:
            self.registered_types = {t.__qualname__: t for t in registered_types}

        def to_dcb_event(self, event: Tagged[Decision]) -> DCBEvent:
            return DCBEvent(
                type=type(event.decision).__qualname__,
                data=json.dumps(event.decision.as_dict()),
                tags=event.tags,
            )

        def to_domain_event(self, event: DCBEvent) -> Tagged[TDecision]:
            return Tagged(
                tags=event.tags,
                decision = self.registered_types[event.type](**json.loads(event.data))
            )


    json_mapper = JSONMapper(
        registered_types=[
            StudentRegistered,
            CourseRegistered,
        ]
    )

    # Convert from tagged decision to DCB event.
    dcb_event = json_mapper.to_dcb_event(tagged_decision)

    # Convert from DCB event to tagged decision.
    tagged_decision = json_mapper.to_domain_event(dcb_event)


Usually this requires some kind of alignment with the decision classes. For example,
the module :mod:`eventsourcing.dcb.msgpack` defines a mapper and decision base classes
that work together using the super fast and compact `msgpack <https://msgpack.org>`_ format.
To use this module, you will need to install the `Python msgspec package <https://pypi.org/project/msgspec/>`_.

.. code-block:: python

    from eventsourcing.dcb.msgpack import Decision, MessagePackMapper, InitialDecision


    class StudentJoinedCourse(Decision):
        student_id: str
        course_id: str


    msgpack_mapper = MessagePackMapper()

    tagged_decision = Tagged(
        tags=["student:123", "course:456"],
        decision=StudentJoinedCourse(
            student_id="student:123",
            course_id="course:123",
        )
    )

    dcb_event = msgpack_mapper.to_dcb_event(tagged_decision)

    tagged_decision = msgpack_mapper.to_domain_event(dcb_event)

.. _DCB Selector:

Selector
--------

A :class:`~eventsourcing.dcb.domain.Selector` defines a criterion for a consistency boundary
in a domain model, in terms of :ref:`decisions <DCB decision>` types and tag strings. It corresponds to the
lower-level :ref:`query item <DCB query item>`.

.. code-block:: python

    from eventsourcing.dcb.domain import Selector

    student_selector = Selector(
        types=[StudentRegistered],
        tags=["student:123"],
    )

    course_selector = Selector(
        types=[CourseRegistered],
        tags=["course:456"],
    )


A list of selectors corresponds to the lower-level :ref:`query <DCB query>`.

.. code-block:: python

    student_consistency_boundary = [student_selector]


.. _DCB Event store:

Event store
-----------

A :class:`~eventsourcing.dcb.persistence.DCBEventStore` encapsulates both a :ref:`mapper <DCB Mapper>` and a :ref:`recorder <DCB Recorders>`.
It has methods for reading and appending tagged decisions.

The :func:`~eventsourcing.dcb.persistence.DCBEventStore.read` method returns an iterator of matching
tagged events. The optional ``cb`` parameter is a consistency boundary for selecting events.
The argument can be either a list of selectors, or an individual selector. The optional ``after`` parameter
is a sequence number after which events will be read.

The :func:`~eventsourcing.dcb.persistence.DCBEventStore.append` method has an ``events`` parameter, which
is a list of tagged decisions. The optional ``cb`` parameter is a consistency boundary
for detecting conflicting events. The argument can be either a list of selectors, or an individual selector.
The optional ``after`` parameter represents a sequence number after which conflicting events will be detected.

.. code-block:: python

    from eventsourcing.dcb.persistence import DCBEventStore

    event_store = DCBEventStore(
        mapper=json_mapper,
        recorder=in_memory_recorder,
    )

    # Read already appended student events.
    student_events = event_store.read(
        cb=student_selector,
    )

    # Append new course events.
    event_store.append(
        events=[tagged_decision],
        cb=course_selector,
    )

    # Read already appended course events.
    course_events = event_store.read(
        cb=course_selector,
    )


.. _Perspective:

Perspective
-----------

The class :class:`~eventsourcing.dcb.domain.Perspective` is an base class for different
kinds of decision models. It defines an interface for defining consistency boundaries,
for keeping track of a "last known position", and has methods for appending new decisions
to an internal list, and for collecting all new tagged decisions.

.. code-block:: python

    from eventsourcing.dcb.domain import Perspective

    class MyPerspective(Perspective):
        def consistency_boundary(self) -> list[Selector]:
            return [Selector(tags=["tag1"]), Selector(tags=["tag2"])]


    my_perspective = MyPerspective()

    # Get consistency boundary.
    cb = my_perspective.consistency_boundary()

    # Append new decision.
    my_perspective.append_new_decision(
        Tagged(
            tags=["tag1", "tag2"],
            decision=Decision(),
        ),
    )

    # Collect new decisions.
    new_decisions = my_perspective.collect_new_decisions()

.. _Enduring object:

Enduring object
---------------

The generic base class :class:`~eventsourcing.dcb.domain.EnduringObject` extends the :ref:`perspective <Perspective>` class
and is is very similar to :doc:`event-sourced aggregates </topics/tutorial/part2>`. Each instance has a unique continuity ID,
which is used generate a consistency boundary and to tag new decisions.

Enduring objects can have command methods decorated with the library's :ref:`event decorator <Event decorator>`.
Calling a decorated command methods will generate a new tagged decision. The command method bodies contribute to
defining a projection of tagged events into the current state of the enduring object. The
:func:`~eventsourcing.dcb.domain.Perspective.collect_new_decisions` method defined by the perspective
base class can be used to collect uncommitted new decisions.

.. code-block:: python

    from eventsourcing.domain import event
    from eventsourcing.dcb.domain import EnduringObject


    class Student(EnduringObject[Decision, str]):
        class Registered(InitialDecision):
            student_id: str
            name: str
            max_courses: int

        class NameUpdated(Decision):
            name: str

        @event(Registered)
        def __init__(self, name: str, max_courses: int) -> None:
            self.name = name
            self.max_courses = max_courses
            self.course_ids: list[str] = []

        @event(NameUpdated)
        def _(self, name: str) -> None:
            self.name = name

        @event(StudentJoinedCourse)
        def _(self, course_id: str) -> None:
            self.course_ids.append(course_id)


    class Course(EnduringObject[Decision, str]):
        class Registered(InitialDecision):
            course_id: str
            name: str
            max_students: int

        def __init__(self, name: str, max_students: int) -> None:
            self.name = name
            self.max_students = max_students
            self.student_ids: list[str] = []

        @event(StudentJoinedCourse)
        def _(self, student_id: str) -> None:
            self.student_ids.append(student_id)


    student = Student(
        name="Sara",
        max_courses=5,
    )

    course = Course(
        name="History",
        max_students=30,
    )

See the :doc:`DCB examples </topics/examples/dcb-enrolment-with-enduring-objects>` for a more complete example.

The advantage of enduring objects is the conceptual unity of having everything together in one place.
However, this aligns enduring objects with the central criticism of event-sourced aggregates motivating DCB:
that including all events in the consistency boundary, regardless of whether they are actually required for
any particular operation, increases contention unnecessarily. Following this comes the accumulation of all
commands and queries in a single class, tending towards large units of code that are hard to understand.
See :ref:`slices <Slice>` for an alternative higher-level abstraction.


.. _Group:

Group
-----

The :class:`~eventsourcing.dcb.domain.Group` class is a base class for cross-cutting decision-making across
many enduring objects. A group defines a consistency boundary that is the union of the consistency boundaries
of the enduring objects in the group.

A group is constructed with already existing enduring objects. Its command methods can trigger new tagged
decisions, using the :func:`~eventsourcing.dcb.domain.Group.trigger_event` method. They will be immediately
applied to all the enduring objects in the group. If an enduring object's projection includes that decision,
its state will be evolved.

Tagged decisions triggered by a group will each be tagged with all the continuity IDs of the enduring objects
in the group. Because of this, they will also be included whenever the enduring objects is subsequently
reconstructed.

.. code-block:: python

    from eventsourcing.dcb.domain import Group


    class StudentAndCourse(Group[Decision]):
        def __init__(
            self,
            student: Student | None,
            course: Course | None,
        ) -> None:
            self.student = student
            self.course = course

        def student_joins_course(self) -> None:
            # Enforce business rules.
            assert len(self.student.course_ids) < self.student.max_courses
            assert len(self.course.student_ids) < self.course.max_students
            assert self.student.id not in self.course.student_ids
            # The DCB magic: one event for "one fact".
            self.trigger_event(
                StudentJoinedCourse,
                student_id=self.student.id,
                course_id=self.course.id,
            )


    group = StudentAndCourse(student, course)
    group.student_joins_course()

    assert student.id in course.student_ids
    assert course.id in student.course_ids

Using groups to trigger cross-cutting events demonstrates the "one fact magic" of DCB. However, because
the consistency boundary for a group is the union of the consistency boundaries for the members of a
group, the criticism of :ref:`enduring objects <Enduring object>` applies even more to groups: that
including all events in the consistency boundary, regardless of whether they are actually required for
any particular operation, increases contention unnecessarily.

.. _Slice:

Slice
-----

The class :class:`~eventsourcing.dcb.domain.Slice` is designed to support "vertical slice architecture" with DCB.
It extends the :class:`~eventsourcing.dcb.domain.Perspective` class. The idea of "vertical slices" is that individual
use cases can be implemented with pieces of code that are entirely independent of each other.
Slices can support both command and query use cases.

The three important aspects of a slice are:

* **Consistency Boundary** — Implement :func:`~eventsourcing.dcb.domain.Perspective.consistency_boundary` to return :ref:`selectors <DCB Selector>`.

* **Projection** — Use the :ref:`event decorator <Event decorator>` to define how selected :ref:`decisions <DCB decision>` evolve state.

* **Command Action** — Implement :func:`~eventsourcing.dcb.domain.Slice.execute` to generate new :ref:`decisions <DCB decision>`.

The consistency boundary for a slice can be used both to select events for the slice's projection, if it has one,
and to select conflicting events when appending any new events to an event store.

The example below shows a slice for updating a student's name. The :func:`~eventsourcing.dcb.domain.Perspective.consistency_boundary`
involves decision classes mentioned in the projection, in this case by using the :data:`projected_types` attribute which
automatically collects all decision classes mentioned in the slice's :func:`@event <eventsourcing.domain.event>` decorators.

.. code-block:: python

    from eventsourcing.dcb.domain import Slice

    class UpdateStudentName(Slice[Decision]):
        def __init__(self, student_id: StudentID, new_name: str) -> None:
            self.student_id = student_id
            self.new_name = new_name
            self.name = ""
            self.student_was_registered: bool = False

        def consistency_boundary(self) -> Selector:
            return Selector(
                types=self.projected_types,
                tags=[self.student_id],
            )

        @event(Student.Registered)
        def _(self, name: str) -> None:
            self.name = name
            self.student_was_registered = True

        @event(Student.NameUpdated)
        def _(self, name: str) -> None:
            self.name = name

        def execute(self) -> None:
            assert self.student_was_registered
            assert self.name != self.new_name
            self.trigger_event(
                Student.NameUpdated,
                tags=[self.student_id],
                name=self.new_name,
            )

See the :doc:`DCB examples </topics/examples/dcb-enrolment-with-vertical-slices>` for a more complete set of examples.

The advantage of using slices is that individual use cases can be implemented with pieces of code that are
entirely independent of each other, and with consistency boundaries that include only what it necessary. However,
this may come at the cost of some repetition of business logic, increasing the volume of code, which tends to
increase the chances of introducing coding errors. See :ref:`enduring objects <Enduring object>` for an alternative
higher-level abstraction.

Mixing styles
-------------

The decision classes used in the ``UpdateStudentName`` slice are those defined above on the ``Student`` enduring
object. In these examples, the decision classes are defined as nested classes, but defining them as module-level
classes would work just as well.

This shows that it is possible to develop a domain model with enduring objects and rework your code to use slices.
Similarly, with a little care, it is possible to start with slices and rework your code to use enduring objects.

Indeed, it is possible to have some parts of your domain model defined with
enduring objects and groups, and other parts defined using slices. This is demonstrated in the
:ref:`example application <DCB application>` below.


.. _DCB Repository:

Repository
----------

The :class:`~eventsourcing.dcb.application.DCBRepository` class supports :ref:`perspectives <perspective>`. A repository is constructed with an :ref:`event store <DCB event store>`.

.. code-block:: python

    from eventsourcing.dcb.application import DCBRepository

    repository = DCBRepository(
        eventstore=DCBEventStore(
            mapper=MessagePackMapper(),
            recorder=InMemoryDCBRecorder(),
        ),
    )

The :func:`~eventsourcing.dcb.application.DCBRepository.save` method collects and appends new decisions.

..
    #include-when-testing
..
    from eventsourcing.utils import clear_topic_cache
    clear_topic_cache()

.. code-block:: python

    student = Student(
        name="Sara",
        max_courses=5,
    )

    course = Course(
        name="History",
        max_students=30,
    )

    repository.save(student)
    repository.save(course)


The :func:`~eventsourcing.dcb.application.DCBRepository.get` method reconstructs an :ref:`enduring object <enduring object>`
for a given continuity ID.

.. code-block:: python

    student = repository.get(student.id)
    course = repository.get(course.id)

    assert student.name == "Sara"
    assert student.max_courses == 5
    assert student.course_ids == []

    assert course.name == "History"
    assert course.max_students == 30
    assert course.student_ids == []


The :func:`~eventsourcing.dcb.application.DCBRepository.get_many` method reconstructs many enduring objects
for a given sequence of continuity IDs.

.. code-block:: python

    student, course = repository.get_many(student.id, course.id)

    assert student.name == "Sara"
    assert student.max_courses == 5
    assert student.course_ids == []

    assert course.name == "History"
    assert course.max_students == 30
    assert course.student_ids == []


The :func:`~eventsourcing.dcb.application.DCBRepository.get_group` method constructs a :ref:`group <group>`
for a given group class and sequence of continuity IDs.

.. code-block:: python

    group = repository.get_group(StudentAndCourse, student.id, course.id)
    group.student_joins_course()

    repository.save(group)

    # Check the student has joined the course.
    student = repository.get(student.id)
    course = repository.get(course.id)
    assert course.id in student.course_ids
    assert student.id in course.student_ids


The :func:`~eventsourcing.dcb.application.DCBRepository.advance` method selects and applies
decisions to a perspective. It can be used to update a :ref:`slice <slice>` to its current
state before calling its :ref:`execute <slice>` method.

.. code-block:: python

    update_student_name = UpdateStudentName(student_id=student.id, new_name="Sara P")
    assert update_student_name.name == ""
    assert update_student_name.student_was_registered is False

    repository.advance(update_student_name)
    assert update_student_name.name == "Sara"
    assert update_student_name.student_was_registered is True

    update_student_name.execute()
    assert update_student_name.name == "Sara P"
    assert update_student_name.student_was_registered is True

    repository.save(update_student_name)

.. _DCB application:

Application
-----------

An application object brings together a stand-alone domain model and supportive persistence infrastructure,
and implements commands and queries that support user interfaces.

Just like the library's original :ref:`application class <Application objects>`,
:class:`~eventsourcing.dcb.application.DCBApplication` selects and constructs a
DCB :ref:`recorder <DCB recorders>` at run-time, according to its environment variable configuration.
This means we can define a DCB application independently of persistence infrastructure, and then run it
in different ways at different times.

The :class:`~eventsourcing.dcb.application.DCBApplication` class also supports the higher-level
abstractions described above. It has a :ref:`repository <DCB repository>` to support working
with perspectives. It also has a method :func:`~eventsourcing.dcb.application.DCBApplication.do`
which supports working with :ref:`slices <Slice>` by advancing and executing a slice, then saving new decisions.

It is also possible to use the :ref:`basic DCB objects <DCB objects>` directly with an application, and to extend
:class:`~eventsourcing.dcb.application.DCBApplication` to support any other higher-level style you may wish to invent.

The example below shows how to write command and query methods using :ref:`enduring objects <enduring object>`,
:ref:`groups <group>`, and :ref:`slices <slice>`.

.. code-block:: python

    from eventsourcing.dcb.application import DCBApplication


    class CourseSubscriptions(DCBApplication):
        def register_student(self, name: str) -> str:
            student = Student(name=name, max_courses=5)
            self.repository.save(student)
            return student.id

        def update_student_name(self, student_id: str, new_name: str) -> None:
            self.do(UpdateStudentName(student_id, new_name))

        def register_course(self, name: str) -> str:
            course = Course(name=name, max_students=30)
            self.repository.save(course)
            return course.id

        def enrol_student_on_course(self, student_id: str, course_id: str) -> None:
            group = self.repository.get_group(StudentAndCourse, student_id, course_id)
            group.student_joins_course()
            self.repository.save(group)

        def list_courses_for_student(self, student_id: str) -> list[str]:
            student: Student = self.repository.get(student_id)
            return [c.name for c in self.repository.get_many(*student.course_ids)]

        def list_students_for_course(self, course_id: str) -> list[str]:
            course: Course = self.repository.get(course_id)
            return [s.name for s in self.repository.get_many(*course.student_ids)]


    # Construct app to use MessagePack and in-memory persistence.
    app = CourseSubscriptions(env={
        "PERSISTENCE_MODULE": "eventsourcing.dcb.popo",
        "MAPPER_TOPIC": "eventsourcing.dcb.msgpack:MessagePackMapper",
    })

    # Construct enduring objects.
    student_id = app.register_student("Sara")
    course_id = app.register_course("History")

    # Update the student name using a vertical slice.
    app.update_student_name(student_id, "Sara P")

    # Enrol the student on the course using a group.
    app.enrol_student_on_course(student_id, course_id)

    # Query for student and course names.
    assert "Sara P" in app.list_students_for_course(course_id)
    assert "History" in app.list_courses_for_student(student_id)

See :ref:`read the examples pages <Dynamic Consistency Boundaries>` for more discussion and examples of DCB.


Code reference
==============

.. automodule:: eventsourcing.dcb.api
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:
    :special-members: __init__

.. automodule:: eventsourcing.dcb.application
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:
    :special-members: __init__

.. automodule:: eventsourcing.dcb.domain
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:
    :special-members: __init__

.. automodule:: eventsourcing.dcb.persistence
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:
    :special-members: __init__

.. automodule:: eventsourcing.dcb.popo
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:
    :special-members: __init__

.. automodule:: eventsourcing.dcb.postgres_tt
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:
    :special-members: __init__

.. automodule:: eventsourcing.dcb.msgpack
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:
    :special-members: __init__
