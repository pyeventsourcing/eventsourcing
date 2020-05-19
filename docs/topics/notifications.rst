=============
Notifications
=============

This section discusses how to use notifications to
propagate the domain events of an application.

If the domain events of an application can somehow be placed in a
sequence, then the sequence of events can be propagated as a sequence
of notifications.

.. contents:: :local:

Three options
-------------

Vaughn Vernon suggests in his book Implementing Domain Driven Design:

.. pull-quote::

    *"at least two mechanisms in a messaging solution must always be consistent with each other: the persistence
    store used by the domain model, and the persistence store backing the messaging infrastructure used to forward
    the Events published by the model. This is required to ensure that when the model’s changes are persisted, Event
    delivery is also guaranteed, and that if an Event is delivered through messaging, it indicates a true situation
    reflected by the model that published it. If either of these is out of lockstep with the other, it will lead to
    incorrect states in one or more interdependent models"*

He continues by describing three options. The first option is to
have the messaging infrastructure and the domain model share
the same persistence store, so changes to the model and
insertion of new messages commit in the same local transaction.

The second option is to have separate datastores for domain
model and messaging but have a two phase commit, or global
transaction, across the two.

The third option is to have the bounded context control
notifications. The simple logic of an ascending sequence
of integers can allow others to progress along an application's
sequence of events. It is also possible to use timestamps.

The first option implies that each event sourced application
functions cohesively also as a messaging service. Assuming that
"messaging service" means an AMQP system, it seems impractical
in a small library such as this to implement an AMQP broker,
something that works with all of the library's record manager
classes. However, perhaps if Kafka could be adapted as a record manager,
it could be used both to persist and propagate events.

The second option, which is similar to the first, involves using a
separate messaging infrastructure within a two-phase commit, which
could be possible, but seems unattractive. At least RabbitMQ can't
participate in a two-phase commit.

The third option is pursued below.

Bounded context controls notifications
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The third option doesn't depend on messaging infrastructure, but does
involve "notifications". If the events of an application can be placed
in a sequence, the sequence of events can be presented as a sequence of
notifications, with notifications being propagated in a standard way.
For example, notifications could be presented by a server, and clients
could pull notifications they don't have, in linked sections, perhaps
using a standard format and standard protocols.

Pulling new notifications could resume whenever a "prompt" is received
via an AMQP system. This way, the client doesn't have the latency or
intensity of a polling interval, the messaging infrastructure doesn't need
to deliver messages in order (which AMQP messaging systems don't normally
provide), and message size is minimised.

If the "substantive" changes enacted by a receiver are stored atomically with
the position in the sequence of notifications, the receiver can resume by
looking at the latest record it has written, and from that record identify
the next notification to consume. This is obvious when considering pure
replication of a sequence of events. But in general, by storing in the produced
sequence the position of the receiver in the consumed sequence, and using
optimistic concurrency control when records are inserted in the produced
sequence, at least from the point of view of consumers of the produced
sequence, "exactly once" processing can be achieved. Redundant (concurrent)
processing of the same sequence would then be possible, which may help
to avoid interruptions in processing the application's events.

If placing all the events in a single sequence is restrictive,
then perhaps partitioning the application notifications may offer a
scalable approach. For example, if each user's work is independent of
the others', then each could have one partition, each notification sequence
would contain all events from the aggregates pertaining to one user. So
that the various sequences can be discovered, it would be useful to have
a sequence in which the creation of each partition is recorded. The
application could then be scaled by partition.

If partitioning the aggregates of application is restrictive, perhaps
because each user's work is dependent on the others', then it
might be possible to have a notification sequence for each aggregate; in
this case, the events would already have been placed in a sequence and so they
could be presented directly as notifications. But as aggregates come and go,
the overhead of keeping track of the notification sequences may become restrictive.

Another possibility would be to sequence the lists of events published when saving
the pending events of an aggregate (see :class:`~eventsourcing.domain.model.aggregate.BaseAggregateRoot`),
so that in cases where it is feasible to place all the commands in a sequence, it would also be feasible
to place the resulting lists of events for each command in a sequence. Sequencing
the lists would allow these little units of coherence to be propagated atomically,
which may be useful in some cases. (Please note, the library doesn't currently support
atomic notification of collections of events, instead each event is notified individually.)

Before continuing with code examples below, we need to setup an event store.

.. code:: python

    from uuid import uuid4

    from eventsourcing.application.policies import PersistencePolicy
    from eventsourcing.domain.model.entity import DomainEntity
    from eventsourcing.infrastructure.eventstore import EventStore
    from eventsourcing.infrastructure.repositories.array import BigArrayRepository
    from eventsourcing.infrastructure.sequenceditem import StoredEvent
    from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
    from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemyDatastore, SQLAlchemySettings
    from eventsourcing.infrastructure.sqlalchemy.manager import SQLAlchemyRecordManager
    from eventsourcing.infrastructure.sqlalchemy.records import StoredEventRecord

    # Setup the database.
    datastore = SQLAlchemyDatastore(
        settings=SQLAlchemySettings(),
        tables=[StoredEventRecord],
    )
    datastore.setup_connection()
    datastore.setup_tables()

    # Setup the record manager.
    record_manager = SQLAlchemyRecordManager(
        session=datastore.session,
        record_class=StoredEventRecord,
        sequenced_item_class=StoredEvent,
        contiguous_record_ids=True,
        application_name=uuid4().hex,
    )

    # Setup a sequenced item mapper.
    sequenced_item_mapper = SequencedItemMapper(
        sequenced_item_class=StoredEvent,
    )

    # Setup the event store.
    event_store = EventStore(
        record_manager=record_manager,
        event_mapper=sequenced_item_mapper
    )

    # Set up a persistence policy.
    persistence_policy = PersistencePolicy(
        event_store=event_store,
        persist_event_type=DomainEntity.Event
    )

Please note, the
:class:`~eventsourcing.infrastructure.sqlalchemy.manager.SQLAlchemyRecordManager` is has its
``contiguous_record_ids`` option enabled.

The infrastructure classes are explained in other sections of this documentation.


Application sequence
--------------------

The fundamental concern here is to propagate the events of
an application without events being missed, duplicated, or jumbled.

The events of an application sequence could be sequenced with
either timestamps or integers. Sequencing the application events
by timestamp is supported by the relational timestamp sequenced
record classes, in that their position column is indexed.
However, the notification logs only work with integer sequences.

Sequencing with integers involves generating a sequence of integers,
which is easy to follow, but can limit the rate at which records
can be written. Using timestamps allows records to be inserted
independently of others, but timestamps can cause uncertainty when
following the events of an application.

If an application's domain model involves the library's
:class:`~eventsourcing.domain.model.aggregate.BaseAggregateRoot`
class, which publishes all pending events together as a list, rather than
inserting each event, it would be possible to insert the lists of events
into the application sequence as a single entry. This may reduce the number
of inserts into the application sequence. However since this library uses
one table with two indexes for the aggregate and application sequence,
perhaps the greatest benefit would be processing these atomically a list
of events that have been created atomically. That might avoid projections
being in an intermediate state such that a user could view only some of the
effects of an action when that would be alarming. This isn't implemented at
time of writing.

Timestamps
~~~~~~~~~~

If time itself was ideal, then timestamps would be ideal. Each event
could then have a timestamp that could be used to index and iterate
through the events of the application. However, there are many
clocks, and each runs slightly differently from the others.

If the timestamps of the application events are created by different
clocks, then it is possible to write events in an order that creates
consistency errors when reconstructing the application state. Hence it is also
possible for new records to be written with a timestamp that is earlier than the
latest one, which makes following the application sequence tricky.

A "jitter buffer" can be used, otherwise any events timestamped by a relatively
retarded clock, and hence positioned behind events that were inserted earlier, could
be missed. The delay, or the length of the buffer, must be greater than the
differences between clocks, but how do we know for sure what is the maximum
difference between the clocks?

Of course, there are lots of remedies. Clocks can be synchronised, more or less.
A timestamp server could be used, and hybrid monotonically increasing timestamps
can implemented. Furthermore, the risk of simultaneous timestamps can be mitigated
by using a random component to the timestamp, as with UUID v1 (which randomizes the
order of otherwise "simultaneous" events).

These techniques (and others) are common, widely discussed, and entirely legitimate
approaches to the complications encountered when using timestamps to sequence events.
The big advantage of using timestamps is that you don't need to generate a sequence
of integers, and applications can be distributed and scaled without performance being
limited by a fragile single-threaded auto-incrementing integer-sequence bottleneck.

In support of this approach, the library's relational record classes for timestamp
sequenced items. In particular, the ``TimestampSequencedRecord`` classes for SQLAlchemy
and Django index their position field, which is a timestamp, and so this index can be
used to get all application events ordered by timestamp. If you use this class in this
way, make sure your clocks are in sync, and query events from the last position until
a time in the recent past, in order to implement a jitter buffer.

.. Todo: Code example.

.. (An improvement could be to have a  timestamp field that is populated
.. by the database server, and index that instead of the application event's
.. timestamp which would vary according to the variation between the clock
.. of application servers. Code changes and other suggestions are always welcome.)

Integers
~~~~~~~~

To reproduce an application's sequence of events perfectly, without any risk
of gaps or duplicates or jumbled items, or race conditions, it seems that we
need to generate and then follow a contiguous sequence of integers. It is also
possible to generate and follow a non-contiguous sequence of integers, but the
gaps will need to be negotiated, by guessing how long an unusually slow write
would take to become visible, since such gaps could be filled in the future.

The library's relational record managers have record classes that have an indexed
integer ID column. Record IDs are used to place all the application's event records
in a single sequence. This technique is recommended for enterprise applications, and
at least the earlier stages of more ambitious projects. There is an inherent limit
to the rate at which an application can write events using this technique, which
essentially follows from the need to write events in series. The rate limit is the
reciprocal of the time it takes to write one event record, which depends on the insert
statement.

By default, these library record classes have an auto-incrementing ID, which will
generate an increasing sequence as records are inserted, but which may have gaps if an
insert fails. Optionally, the record managers can also can be used to generate contiguous
record IDs, with an "insert select from" SQL statement that, as a clause in the insert
statement, selects the maximum record ID from the visible table records. Since it is
only possible to extend the sequence, the visible record IDs will form a contiguous
sequence, which is the easiest thing to follow, because there is no possibility for
race conditions where events appear behind the last visible event. The "insert select from"
statement will probably be slower than the default "insert values" and the auto-incrementing
ID, and only one of many concurrent inserts will be successful. Exceptions from concurrent
inserts could be mitigated with retried, and avoided entirely by serialising the inserts
with a queue, for example in an actor framework. Although this will smooth over spikes,
and unfortunate coincidences will be avoided, the continuous maximum throughput will not
be increased, a queue will eventually reach a limit and a different exception will be raised.

Given the rate limit, it could take an application quite a long time to fill up
a well provisioned database table. Nevertheless, if the rate of writing or the volume
of domain event records in your system inclines you towards partitioning the table
of stored events, or if anyway your database works in this way (e.g. Cassandra), then the
table would need to be partitioned by sequence ID so that the aggregate performance
isn't compromised by having its events distributed across partitions, which means
maintaining an index of record IDs across such partitions, and hence sequencing
the events of an application in this way, will be problematic.

To proceed without an indexed record ID column, the library class ``BigArray``
can be used to sequence all the events of an application. This technique
can be used as an alternative to using a native database index of record IDs,
especially in situations where a normal database index across all records is
generally discouraged (e.g. in Cassandra), or where records do not have an
integer ID or timestamp that can be indexed (e.g. all the library's record
classes for Cassandra, and the ``IntegerSequencedNoIDRecord`` for SQLAlchemy,
or when storing an index for a large number of records in a single partition
is undesirable for infrastructure or performance reasons, or is not supported
by the database.

The ``BigArray`` can be used to construct both contiguous and non-contiguous
integer sequences. As with the record IDs above, if each item is positioned in the
next position after the last visible record, then a contiguous sequence is generated,
but at the cost of finding the last visible record. However, if a number generator
is used, the rate is limited by the rate at which numbers can be issued, but if inserts
can fail, then numbers can be lost and the integer sequence will have gaps.

Record managers
~~~~~~~~~~~~~~~

A relational record manager can function as an application sequence,
especially when its record class has an ID field, and more so when the
``contiguous_record_ids`` option is enabled. This technique ensures
that whenever an entity or aggregate command returns successfully,
any events will already have been simultaneously placed in both the
aggregate's and the application's sequence. Importantly, if inserting
an event hits a uniqueness constraint and the transaction is rolled
back, the event will not appear in either sequence.

This approach provides perfect accuracy with great simplicity for
followers, but it has a maximum total rate at which records can be
written into the database. In particular, the ``contiguous_record_ids``
feature executes an "insert select from" SQL statement that generates
contiguous record IDs when records are inserted, on the database-side
as a clause in the insert statement, by selecting the maximum existing
ID in the table, adding one, and inserting that value, along with the
event data.

Because the IDs must be unique, applications may experience the library's
``ConcurrencyError`` exception if they happen to insert records
simultaneously with others. Record ID conflicts are retried a finite
number of times by the library before a ``ConcurrencyError`` exception
is raised. But with a load beyond the capability of a service, increased
congestion will be experienced by the application as an increased frequency
of concurrency errors.

Please note, without the ``contiguous_record_ids`` feature enabled,
the ID columns of library record classes should be merely auto-incrementing,
and so the record IDs can anyway be used to get all the records in
the order they were written. However, auto-incrementing the ID can lead to
a sequence of IDs that has gaps, a non-contiguous sequence, which could lead
to race conditions and missed items. The gaps would need to be negotiated,
which is relatively complicated. To keep things relatively simple, a record
manager that does not have the ``contiguous_record_ids`` feature enabled cannot
be used with the library class
:class:`~eventsourcing.application.notificationlog.RecordManagerNotificationLog`
(introduced below). If you want to sequence the application events with a non-contiguous
sequence, then you will need to write something that can negotiate the gaps.

To use contiguous IDs to sequence the events of an application, simply use a
relational record manager with an ``IntegerSequencedRecord`` that has an ID,
such as the ``StoredEventRecord`` record class, and with a True value for its
``contiguous_record_ids`` constructor argument. The ``record_manager``
above was constructed in this way. The records can be then be obtained
using the ``get_notifications()`` method of the record manager. The record IDs
will form a contiguous sequence, suitable for the :class:`~eventsourcing.application.notificationlog.RecordManagerNotificationLog`


.. code:: python

    from eventsourcing.domain.model.entity import VersionedEntity

    notifications = list(record_manager.get_notifications())

    assert len(notifications) == 0, notifications

    first_entity = VersionedEntity.__create__()

    notifications = list(record_manager.get_notifications(start=0, stop=5))

    assert len(notifications) == 1, notifications

The local notification log class :class:`~eventsourcing.application.notificationlog.RecordManagerNotificationLog`
(see below) can adapt record managers, presenting the
application sequence as notifications in a standard way.


BigArray
~~~~~~~~

This is a long section, and can be skipped if you aren't currently
trying to scale beyond the limits of a database table that has
indexed record IDs.

To support ultra-high capacity requirements, the application sequence must
be capable of having a very large number of events, neither swamping
an individual database partition (in Cassandra) nor distributing
things across table partitions without any particular order so
that iterating through the sequence is slow and expensive. We also want
the application log effectively to have constant time read and write
operations for normal usage.

The library class :class:`~eventsourcing.domain.model.array.BigArray`
satisfies these requirements quite well, by spanning across many such
partitions. It is a tree of arrays, with a root array that stores
references to the current apex, with an apex that contains references
to arrays, which either contain references to lower arrays or contain
the items assigned to the big array. Each array uses one database
partition, limited in size (the array size) to ensure the partition
is never too large. The identity of each array can be calculated directly
from the index number, so it is possible to identify arrays directly
without traversing the tree to discover entity IDs. The capacity of base
arrays is the array size to the power of the array size. For a reasonable
size of array, it isn't really possible to fill up the base of such an
array tree, but the slow growing properties of this tree mean that for
all imaginable scenarios, the performance will be approximately constant
as items are appended to the big array.

Items can be appended to a big array using the ``append()`` method.
The append() method identifies the next available index in the array,
and then assigns the item to that index in the array. A
:class:`~eventsourcing.exceptions.ConcurrencyError` will be raised if
the position is already taken.

The performance of the ``append()`` method is proportional to the log of the
index in the array, to the base of the array size used in the big array, rounded
up to the nearest integer, plus one (because of the root sequence that tracks
the apex). For example, if the sub-array size is 10,000, then it will take only 50%
longer to append the 100,000,000th item to the big array than the 1st one. By
the time the 1,000,000,000,000th index position is assigned to a big array, the
``append()`` method will take only twice as long as the 1st.

That's because the default performance of the ``append()`` method is dominated
by the need to walk down the big array's tree of arrays to find the highest
assigned index. Once the index of the next position is known, the item can be
assigned directly to an array. The performance can be improved by using an integer
sequence generator, but departing from using the current max ID risks creating
gaps in the sequence of IDs.

.. code:: python

    from uuid import uuid4
    from eventsourcing.domain.model.array import BigArray
    from eventsourcing.infrastructure.repositories.array import BigArrayRepository


    repo = BigArrayRepository(
        event_store=event_store,
        array_size=10000
    )

    big_array = repo[uuid4()]
    big_array.append('item0')
    big_array.append('item1')
    big_array.append('item2')
    big_array.append('item3')


Because there is a small duration of time between checking for the next
position and using it, another thread could jump in and use the position
first. If that happens, a :class:`~eventsourcing.exceptions.ConcurrencyError`
will be raised by the :class:`~eventsourcing.domain.model.array.BigArray`
object. In such a case, another attempt can be made to append the item.

Items can be assigned directly to a big array using an index number. If
an item has already been assigned to the same position, a concurrency error
will be raised, and the original item will remain in place. Items cannot
be unassigned from an array, hence each position in the array can be
assigned once only.

The average performance of assigning an item is a constant time. The worst
case is the log of the index with base equal to the array size, which occurs
when containing arrays are added, so that the last highest assigned index can
be discovered. The probability of departing from average performance is
inversely proportional to the array size, since the arger the array
size, the less often the base arrays fill up. For a decent array size,
the probability of needing to build the tree is very low. And when the tree
does need building, it doesn't take very long (and most of it probably already
exists).

.. code:: python

    from eventsourcing.exceptions import ConcurrencyError

    assert big_array.get_next_position() == 4

    big_array[4] = 'item4'
    try:
        big_array[4] = 'item4a'
    except ConcurrencyError:
        pass
    else:
        raise


If the next available position in the array must be identified
each time an item is assigned, the amount of contention will increase
as the number of threads increases. Using the ``append()`` method alone
will work if the time period of appending events is greater than the
time it takes to identify the next available index and assign to it.
At that rate, any contention will not lead to congestion. Different
nodes can take their chances assigning to what they believe is an
unassigned index, and if another has already taken that position,
the operation can be retried.

However, there will be an upper limit to the rate at which events can be
appended, and contention will eventually lead to congestion that will cause
requests to backup or be spilled.

The rate of assigning items to the big array can be greatly increased
by factoring out the generation of the sequence of integers. Instead of
discovering the next position from the array each time an item is assigned,
an integer sequence generator can be used to generate a contiguous sequence
of integers. This technique eliminates contention around assigning items to
the big array entirely. In consequence, the bandwidth of assigning to a big
array using an integer sequence generator is much greater than using the
``append()`` method.

If the application is executed in only one process, for example during development,
the number generator can be a simple Python object. The library class
:class:`~eventsourcing.infrastructure.integersequencegenerators.base.SimpleIntegerSequenceGenerator`
generates a contiguous sequence of integers that can be shared across multiple
threads in the same process.

.. code:: python

    from eventsourcing.infrastructure.integersequencegenerators.base import SimpleIntegerSequenceGenerator

    integers = SimpleIntegerSequenceGenerator()
    generated = []
    for i in integers:
        if i >= 5:
            break
        generated.append(i)

    expected = list(range(5))
    assert generated == expected, (generated, expected)


If the application is deployed across many nodes, an external integer sequence
generator can be used. There are many possible solutions. The library class
:class:`~eventsourcing.infrastructure.integersequencegenerators.redisincr.RedisIncr`
uses Redis' INCR command to generate a contiguous sequence of integers
that can be shared be processes running on different nodes.

Using Redis doesn't necessarily create a single point of failure. Redundancy can be
obtained using clustered Redis. Although there aren't synchronous updates between
nodes, so that the INCR command may issue the same numbers more than once, these
numbers can only ever be used once. As failures are retried, the position will
eventually reach an unassigned index position. Arrangements can be made to set the
value from the highest assigned index. With care, the worst case will be an occasional
slight delay in storing events, caused by switching to a new Redis node and catching up
with the current index number. Please note, there is currently no code in the library
to update or resync the Redis key used in the Redis INCR integer sequence generator.

.. code:: python

    from eventsourcing.infrastructure.integersequencegenerators.redisincr import RedisIncr

    integers = RedisIncr()
    generated = []
    for i in integers:
        generated.append(i)
        if i >= 4:
            break

    expected = list(range(5))
    assert generated == expected, (generated, expected)


The integer sequence generator can be used when assigning items to the
big array object.

.. code:: python

    big_array[next(integers)] = 'item5'
    big_array[next(integers)] = 'item6'

    assert big_array.get_next_position() == 7


Items can be read from the big array using an index or a slice.

The performance of reading an item at a given index is always constant time
with respect to the number of the index. The base array ID, and the index of
the item in the base array, can be calculated from the number of the index.

The performance of reading a slice of items is proportional to the
size of the slice. Consecutive items in a base array are stored consecutively
in the same database partition, and if the slice overlaps more than base
array, the iteration proceeds to the next partition.

.. code:: python

    assert big_array[0] == 'item0'
    assert list(big_array[5:7]) == ['item5', 'item6']


The big array can be written to by a persistence policy. References
to events could be assigned to the big array before the domain event is
written to the aggregate's own sequence, so that it isn't possible to store
an event in the aggregate's sequence that is not already in the application
sequence. To do that, construct the application logging policy object before the
normal application persistence policy. Also, make sure the application
log policy excludes the events published by the big array (otherwise there
will be an infinite recursion). If the event fails to write, then the application
sequence will have a dangling reference, which followers will have to cope with.

Alternatively, if the database supports transactions across different tables
(not Cassandra), the big array assignment and the event record insert can be
done in the same transaction, so they both appear or neither does. This will
help to avoid some complexity for followers. The library currently doesn't
have any code that writes to both in the same transaction.

Todo: Code example of policy that places application domain events in a big array.

If the big array item is not assigned in the same separate transaction as
the event record is inserted, commands that fail to insert the event record
after the event has been assigned to the big array (due to an operation error
or a concurrency error) should probably raise an exception, so that the
command is seen to have failed and so may be retried. An event would then
be in the application sequence but not in the aggregate sequence, which is
effectively a dangling reference, one that may or may not be satisfied later.
If the event record insert failed due to an operational error, and the command
is retried, a new event at the same position in the same sequence may be published,
and so it would appear twice in the application sequence. And so, whilst dangling
references in the application log can perhaps be filtered out by followers after
a delay, care should be taken by followers to deduplicate events.

It may also happen that an item fails to be assigned to the big array. In this case,
an ID that was issued by an integer sequence generator would be lost. The result
would be a gap, that would need to be negotiated by followers.

If writing the event to its aggregate sequence is successful, then it is
possible to push a notification about the event to a message queue. Failing
to push the notification perhaps should not prevent the command returning
normally. Push notifications could also be generated by another process,
something that pulls from the application log, and pushes notifications
for events that have not already been sent.

Since we can imagine there is quite a lot of noise in the sequence, it may
be useful to process the application sequence within the context by
constructing another sequence that does not have duplicates or gaps, and
then propagating that sequence.

The local notification log class :class:`~eventsourcing.application.notificationlog.BigArrayNotificationLog`
(see below) can adapt big arrays, presenting the assigned items
as notifications in a standard way. Gaps in the array will result in
notification items of ``None``. But where there are gaps, there
can be race conditions, where the gaps are filled. Only a contiguous
sequence, which has no gaps, can exclude gaps being filled later.

Please note: there is an unimplemented enhancement which
would allow this data structure to be modified in a single transaction,
because the new non-leaf nodes can be determined from the position of
the new leaf node, however currently a less optimal approach is used
which attempts to add all non-leaf nodes and carries on in case of
conflicts.

.. Todo: Implement the big array enhancement: determine non-lead nodes and write all records in single transaction.

Notification logs
-----------------

As described in Implementing Domain Driven Design, a notification log
presents a sequence of notification items in linked sections.

Sections are obtained from a notification log using Python's
"square brackets" sequence index syntax. The key is a section ID.
A special section ID called "current" can be used to obtain a section
which contains the latest notification (see examples below).

Each section contains a limited number items, the size is fixed by
the notification log's ``section_size`` constructor argument. When
the current section is full, it is considered to be an archived section.

All the archived sections have an ID for the next section. Similarly,
all sections except the first have an ID for the previous section.

A client can get the current section, go back until it reaches the
last notification it has already received, and then go forward until
all existing notifications have been received.

The section ID numbering scheme follows Vaughn Vernon's book.
Section IDs are strings: a string formatted
with two integers separated by a comma. The integers represent
the first and last number of the items included in a section.

The classes below can be used to present a sequence of items,
such the domain events of an application, in linked
sections. They can also be used to present other sequences
for example a projection of the application sequence, where the
events are rendered in a particular way for a particular purpose,
such as analytics.

A local notification log could be
presented by an API in a serialized format e.g. JSON or Atom
XML. A remote notification log could then access the API and
provide notification items in the standard way. The serialized
section documents could then be cached using standard cacheing
mechanisms.

Local notification logs
-----------------------

RecordManagerNotificationLog
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A relational record manager can be adapted by the library class
:class:`~eventsourcing.application.notificationlog.RecordManagerNotificationLog`,
which will then present the application's events as notifications.

The :class:`~eventsourcing.application.notificationlog.RecordManagerNotificationLog`
is constructed with a ``record_manager``, and a ``section_size``.

.. code:: python

    from eventsourcing.application.notificationlog import RecordManagerNotificationLog

    # Construct notification log.
    notification_log = RecordManagerNotificationLog(record_manager, section_size=5)

    # Get the "current" section from the record notification log.
    section = notification_log['current']
    assert section.section_id == '6,10', section.section_id
    assert section.previous_id == '1,5', section.previous_id
    assert section.next_id == None
    assert len(section.items) == 4, len(section.items)

    # Get the first section from the record notification log.
    section = notification_log['1,5']
    assert section.section_id == '1,5', section.section_id
    assert section.previous_id == None, section.previous_id
    assert section.next_id == '6,10', section.next_id
    assert len(section.items) == 5, section.items

The notifications (``section.items``) from a
:class:`~eventsourcing.application.notificationlog.RecordManagerNotificationLog`
are Python dicts with keys: ``id``, ``topic``, ``state``, ``originator_id``,
``originator_version``, and ``casual_dependencies``.

A domain event can be obtained from a notification by calling the method
``event_from_topic_and_state()`` on a sequenced item mapper, passing in
the ``topic`` and ``state`` values. The ``topic`` value can be resolved
to a Python class, such as a domain event class. An object instance, such
as a domain event object, can then be reconstructed using the notification's
``state``. The notification's ``state`` is simply the stored event ``state``,
so if the record data was encrypted, the notification data will also be
encrypted. The sequenced item mapper needs to be configured accordingly.

In the code below, the function ``resolve_notifications`` shows
how that can be done (this function doesn't exist in the library).

.. code:: python

    def resolve_notifications(notifications):
        return [
            sequenced_item_mapper.event_from_topic_and_state(
                topic=notification['topic'],
                state=notification['state']
            ) for notification in notifications
        ]

    # Resolve a section of notifications into domain events.
    domain_events = resolve_notifications(section.items)

    from eventsourcing.domain.model.array import ItemAssigned
    assert type(domain_events[0]) == VersionedEntity.Created
    assert type(domain_events[1]) == ItemAssigned
    assert type(domain_events[2]) == ItemAssigned
    assert type(domain_events[3]) == ItemAssigned
    assert type(domain_events[4]) == ItemAssigned

    assert domain_events[0].originator_id == first_entity.id
    assert domain_events[1].item == 'item0'
    assert domain_events[3].item == 'item1'
    assert domain_events[4].item == 'item2'


If the notification data was encrypted by the sequenced item
mapper, the sequenced item mapper will decrypt the data before
reconstructing the domain event. In this example, the sequenced
item mapper does not have a cipher, so the notification data is
not encrypted.

The library's :class:`~eventsourcing.application.simple.SimpleApplication`
has a ``notification_log`` that uses the
:class:`~eventsourcing.application.notificationlog.RecordManagerNotificationLog` class.

.. Todo: Move that function into the library, where? Perhaps subclass
.. NotificationLogReader with EventNotificationLogReader?

Notification records
~~~~~~~~~~~~~~~~~~~~

An application could write separate notification records and event records.
Having separate notification records allows notifications to be arbitrarily
and therefore evenly distributed across a variable set of notification logs.

The number of logs could governed automatically by a scaling process so the
cadence of each notification log is actively controlled to a constant level.

Todo: Merge these paragraphs, remove repetition (params below were moved from projections doc).

When an application has one notification log, any causal ordering between
events will preserved in the log: you won't be informed that something
changed without previously being informed that it was created. But if there
are many notification logs, then it would be possible to record casual
ordering between events: the notifications recorded for the last events
that were applied to the aggregates used when triggering new events can
be included in the notifications for the new events. This avoids downstream
needing to: serialise everything in order to recover order e.g. by merge
sorting all logs by timestamp; partitioning the application state; or to
ignore causal ordering. For efficiency, prior events that were notified in
the same log wouldn't need to be included. So it would make sense for all the
events of a particular aggregate to be notified in the same log, but if necessary
they could be distributed across different notification logs without downstream
processing needing to incoherent or bottle-necked. To scale data, it might become
necessary to fix an aggregate to a notification log, so that many databases can be
used with each having the notification records and the event records together (and
any upstream notification tracking records) so that atomic transactions for
these records are still workable.

If all events in a process are placed in the same notification log sequence, since
a notification log will need to be processed in series, the throughput is more or
less limited by the rate at which a sequence can be processed by a single thread.
To scale throughput, the application event notifications could be distributed into many
different notification logs, and a separate operating system process (or thread)
could run concurrently for each log. A set of notification logs could be processed
by a single thread, that perhaps takes one notification in turn from each log,
but with parallel processing, total throughput could be proportional to the number
of notification logs used to propagate the domain events of an application.

Causal ordering can be maintained across the logs, so long as each event
notification references the notifications for the last event in all the aggregates
that were required to trigger the new events. If a notification references a
notification in another log, then the processing can wait until that other
notification has been processed. Hence notifications do not need to include
notifications in the same log, as they will be processed first. On the other hand,
if all notifications include such references to other notifications, then a notification
log could be processed in parallel: since it is unlikely that each notification
in a log depends on its immediate predecessor, wherever a sub-sequence of notifications all
depend on notifications that have already been processed, those notifications could
perhaps be processed concurrently.

There will be a trade-off between evenly distributing events across the various
logs and minimising the number of causal ordering that go across logs. A simple
and probably effective rule would be to place all the events of one aggregate
in the same log. But it may also help to partition the aggregates of an application
by e.g. user, and place the events of all aggregates created by a user in the same
notification log, since they are perhaps most likely to be causally related. This
mechanism would allow the number of logs to be increased and decreased, with aggregate
event notifications switching from one log to another and still be processed coherently.


BigArrayNotificationLog
~~~~~~~~~~~~~~~~~~~~~~~

You can skip this section if you skipped the section about BigArray.

A big array can be adapted by the library class
:class:`~eventsourcing.application.notificationlog.BigArrayNotificationLog`,
which will then present the items assigned to the array as notifications.

The :class:`~eventsourcing.application.notificationlog.BigArrayNotificationLog`
is constructed with a ``big_array``, and a ``section_size``.

.. code:: python

    from eventsourcing.application.notificationlog import BigArrayNotificationLog

    # Construct notification log.
    big_array_notification_log = BigArrayNotificationLog(big_array, section_size=5)

    # Get the "current "section from the big array notification log.
    section = big_array_notification_log['current']
    assert section.section_id == '6,10', section.section_id
    assert section.previous_id == '1,5', section.previous_id
    assert section.next_id == None
    assert len(section.items) == 2, len(section.items)

    # Check we got the last two items assigned to the big array.
    assert section.items == ['item5', 'item6']

    # Get the first section from the notification log.
    section = big_array_notification_log['1,10']
    assert section.section_id == '1,5', section.section_id
    assert section.previous_id == None, section.previous_id
    assert section.next_id == '6,10', section.next_id
    assert len(section.items) == 5, section.items

    # Check we got the first five items assigned to the big array.
    assert section.items == ['item0', 'item1', 'item2', 'item3', 'item4']

Please note, for simplicity, the items in this example are
just strings ('item0' etc). If the big array is being used to sequence the
events of an application, it is possible to assign just the item's sequence
ID and position, and let followers get the actual event using those references.

Todo: Fix problem with not being able to write all of big array with one
SQL expression, since it involves constructing the non-leaf records. Perhaps
could be more precise about predicting which non-leaf records need to be inserted
so that we don't walk down from the top each time discovering whether or not
a record exists. It's totally predictable, but the code is cautious. But it would
be possible to identify all the new records and add them. Still not really possible
to use "insert select max", but if each log has it's own process, then IDs can
be issued from a generator, initialised from a query, and reused if an insert fails
so the sequence is contiguous.


.. Aggregate notification log
.. ~~~~~~~~~~~~~~~~~~~~~~~~~~

.. Perhaps a more sophisticated approach would be to have many notification logs,
.. with one application log and many aggregate logs. The application log could be
.. used only to notify of the existence of the aggregate logs. However the order
.. of the application events after recombining many aggregate logs into a single
.. sequence would be undefined (can't say jumbled because such events were never placed
.. in a single application sequence). If the notifications had timestamps, the
.. aggregate logs could be merged by timestamp.

.. It might also be useful to partition sets of aggregates, and have a partition log
.. that orders events from all the aggregates in the partition.

.. Todo: In general, discovering the aggregate IDs is important. Perhaps make a
.. method on record manager class that returns all the sequence IDs?

.. Todo: Write local notification log class that can follow the events of an aggregate.

.. Todo: Add support for partitioning the aggregates of an application e.g. by user account.


Remote notification logs
------------------------

The RESTful API design in Implementing Domain Driven Design
suggests a good way to present the notification log, a way that
is simple and can scale using established HTTP technology.

This library has a pair of classes that can help to present a
notification log remotely.

The :class:`~eventsourcing.interface.notificationlog.RemoteNotificationLog`
class has the same interface for getting sections as the local notification
log classes described above, but instead of using a local datasource, it
requests serialized sections from a Web API.

The :class:`~eventsourcing.interface.notificationlog.NotificationLogView`
class serializes sections from a local notification log, and can be used
to implement a Web API that presents notifications to a network.

Alternatively to presenting domain event data and topic information,
a Web API could present only the event's sequence ID and position values,
requiring clients to obtain the domain event from the event store using
those references. If the notification log uses a big array, and the big
array is assigned with only sequence ID and position values, the big array
notification log could be used directly with the
:class:`~eventsourcing.interface.notificationlog.NotificationLogView` to
notify of domain events by reference rather than by value. However, if
the notification log uses a record manager, then a notification log adapter
would be needed to convert the events into the references.

If a notification log would then receive and would also return only sequence
ID and position information to its caller. The caller could then proceed by
obtaining the domain event from the event store. Another adapter could be
used to perform the reverse operation: adapting a notification log
that contains references to one that returns whole domain event objects.
Such adapters are not currently provided by this library.


NotificationLogView
~~~~~~~~~~~~~~~~~~~

The library class :class:`~eventsourcing.interface.notificationlog.NotificationLogView`
presents sections from a local notification log, and can be used to implement a Web API.

The :class:`~eventsourcing.interface.notificationlog.NotificationLogView`
class is constructed with a local ``notification_log`` object and a
``json_encoder`` (for example an instance of the library's
:class:`~eventsourcing.utils.transcoding.ObjectJSONEncoder` class).

The example below uses the record notification log, constructed above.

.. code:: python

    import json

    from eventsourcing.interface.notificationlog import NotificationLogView
    from eventsourcing.utils.transcoding import ObjectJSONEncoder, ObjectJSONDecoder

    view = NotificationLogView(
        notification_log=notification_log,
        json_encoder=ObjectJSONEncoder()
    )

    section_json = view.present_resource('1,5')

    section_dict = ObjectJSONDecoder().decode(section_json.decode('utf8'))

    assert section_dict['section_id'] == '1,5'
    assert section_dict['next_id'] == '6,10'
    assert section_dict['previous_id'] == None
    assert section_dict['items'] == notification_log['1,5'].items
    assert len(section_dict['items']) == 5

    item = section_dict['items'][0]
    assert item['id'] == 1
    assert item['topic'] == 'eventsourcing.domain.model.entity#VersionedEntity.Created'

    assert section_dict['items'][1]['topic'] == 'eventsourcing.domain.model.array#ItemAssigned'
    assert section_dict['items'][2]['topic'] == 'eventsourcing.domain.model.array#ItemAssigned'
    assert section_dict['items'][3]['topic'] == 'eventsourcing.domain.model.array#ItemAssigned'
    assert section_dict['items'][4]['topic'] == 'eventsourcing.domain.model.array#ItemAssigned'

    # Resolve the notifications to domain events.
    domain_events = resolve_notifications(section_dict['items'])

    # Check we got the first entity's "created" event.
    assert isinstance(domain_events[0], VersionedEntity.Created)
    assert domain_events[0].originator_id == first_entity.id


Notification API
~~~~~~~~~~~~~~~~

A Web application could identify a section ID from an HTTP request
path, and respond by returning an HTTP response with JSON
content that represents that section of a notification log.

The example uses the library's :class:`~eventsourcing.interface.notificationlog.NotificationLogView` to
serialize the sections of the record notification log (see above).

.. code:: python

    def notification_log_wsgi(environ, start_response):

        # Identify section from request.
        section_id = environ['PATH_INFO'].strip('/')

        # Construct notification log view.
        view = NotificationLogView(notification_log)

        # Get serialized section.
        section = view.present_resource(section_id)

        # Start HTTP response.
        status = '200 OK'
        headers = [('Content-type', 'text/plain; charset=utf-8')]
        start_response(status, headers)

        # Return body.
        return [(line + '\n').encode('utf8') for line in section.split('\n')]

A more sophisticated application might include
an ETag header when responding with the current section, and
a Cache-Control header when responding with archived sections.

A more standard approach would be to use Atom (application/atom+xml)
which is a common standard for producing RSS feeds and thus a great
fit for representing lists of events, rather than
:class:`~eventsourcing.interface.notificationlog.NotificationLogView`.
However, just as this library doesn't (currently) have any code that
generates Atom feeds from domain events, there isn't any code that
reads domain events from atom feeds. So if you wanted to use Atom
rather than :class:`~eventsourcing.interface.notificationlog.NotificationLogView`
in your API, then you will also need to write a version of
:class:`~eventsourcing.interface.notificationlog.RemoteNotificationLog`
that can work with your Atom API.

RemoteNotificationLog
~~~~~~~~~~~~~~~~~~~~~

The library class :class:`~eventsourcing.interface.notificationlog.RemoteNotificationLog`
can be used in the same way as the local notification logs above. The difference is that
rather than accessing a database using a record manager, it makes requests to an API.

The :class:`~eventsourcing.interface.notificationlog.RemoteNotificationLog`
class is constructed with a ``base_url``, a ``notification_log_id`` and a
``json_decoder_class``. The JSON decoder must be capable of decoding JSON encoded by
the API. Hence, the JSON decoder must match the JSON encoder used by the API.

The default ``json_decoder_class`` is the library class
:class:`~eventsourcing.utils.transcoding.ObjectJSONDecoder`. This encoder
matches the default ``json_encoder_class`` of the library class
:class:`~eventsourcing.interface.notificationlog.NotificationLogView`,
which is also the library class :class:`~eventsourcing.utils.transcoding.ObjectJSONDecoder`.
If you want to extend the JSON encoder classes used here, just make sure they match,
otherwise you will get decoding errors.

The :class:`~eventsourcing.application.notificationlog.NotificationLogReader` can use the
:class:`~eventsourcing.interface.notificationlog.RemoteNotificationLog` in the same way that
it uses a local notification log object. Just construct it with a remote notification log
object, rather than a local notification log object, then read notifications in the same
way (as described above).

If the API uses a :class:`~eventsourcing.interface.notificationlog.NotificationLogView`
to serialise the sections of a local notification log, the remote notification log object
functions effectively as a proxy for a local notification log on a remote node.

.. code:: python

    from eventsourcing.interface.notificationlog import RemoteNotificationLog

    remote_notification_log = RemoteNotificationLog("base_url")

If a server were running at "base_url" the ``remote_notification_log`` would
function in the same was as the local notification logs described above, returning
section objects for section IDs using the square brackets syntax.

If the section objects were created by a
:class:`~eventsourcing.interface.notificationlog.NotificationLogView`
that had the ``notification_log`` above, we could obtain all the events of an
application across an HTTP connection, accurately and without great complication.

See ``test_notificationlog.py`` for an example that uses a Flask app running
in a local HTTP server to get notifications remotely using these classes.


Notification log reader
-----------------------

The library object class
:class:`~eventsourcing.application.notificationlog.NotificationLogReader` effectively
functions as an iterator, yielding a continuous sequence of notifications that
it discovers from the sections of a notification log, local or remote.

A notification log reader object will navigate the linked sections of a notification
log, backwards from the "current" section of the notification log, until reaching the position
it seeks. The position, which defaults to ``0``, can be set directly with the reader's
:func:`~eventsourcing.application.notificationlog.NotificationLogReader.seek`
method. Hence, by default, the reader will navigate all the way back to the
first section.

After reaching the position it seeks, the reader will then navigate forwards, yielding
as a continuous sequence all the subsequent notifications in the notification log.

As it navigates forwards, yielding notifications, it maintains position so that it can
continue when there are further notifications. This position could be persisted, so that
position is maintained across invocations, but that is not a feature of the
class :class:`~eventsourcing.application.notificationlog.NotificationLogReader`,
and would have to be added in a subclass or client object.

The class :class:`~eventsourcing.application.notificationlog.NotificationLogReader`
supports slices. The position is set indirectly when a slice has a start index.

All the notification logs discussed above (local and remote) have the same interface,
and can be used by :class:`~eventsourcing.application.notificationlog.NotificationLogReader`
progressively to obtain unseen notifications.

The example below happens to yield notifications from a big array notification log, but it
would work equally well with a record notification log, or with a remote notification log.

.. code:: python

    from eventsourcing.application.notificationlog import NotificationLogReader

    # Construct log reader.
    reader = NotificationLogReader(notification_log)

    # The position is zero by default.
    assert reader.position == 0

    # The position can be set directly.
    reader.seek(10)
    assert reader.position == 10

    # Reset the position.
    reader.seek(0)

    # Read all existing notifications.
    all_notifications = reader.read_list()
    assert len(all_notifications) == 9

    # Resolve the notifications to domain events.
    domain_events = resolve_notifications(all_notifications)

    # Check we got the first entity's created event.
    assert isinstance(domain_events[0], VersionedEntity.Created)
    assert domain_events[0].originator_id == first_entity.id

    # Check the position has advanced.
    assert reader.position == 9

    # Read all subsequent notifications (should be none).
    subsequent_notifications = list(reader)
    assert subsequent_notifications == []

    # Publish two more events.
    VersionedEntity.__create__()
    VersionedEntity.__create__()

    # Read all subsequent notifications (should be two).
    subsequent_notifications = reader.read_list()
    assert len(subsequent_notifications) == 2

    # Check the position has advanced.
    assert reader.position == 11

    # Read all subsequent notifications (should be none).
    subsequent_notifications = reader.read_list()
    len(subsequent_notifications) == 0

    # Publish three more events.
    VersionedEntity.__create__()
    VersionedEntity.__create__()
    last_entity = VersionedEntity.__create__()

    # Read all subsequent notifications (should be three).
    subsequent_notifications = reader.read_list()
    assert len(subsequent_notifications) == 3

    # Check the position has advanced.
    assert reader.position == 14

    # Resolve the notifications.
    domain_events = resolve_notifications(subsequent_notifications)
    last_domain_event = domain_events[-1]

    # Check we got the last entity's created event.
    assert isinstance(last_domain_event, VersionedEntity.Created), last_domain_event
    assert last_domain_event.originator_id == last_entity.id

    # Read all subsequent notifications (should be none).
    subsequent_notifications = reader.read_list()
    assert subsequent_notifications == []

    # Check the position has advanced.
    assert reader.position == 14

The position could be persisted, and the persisted value could be
used to initialise the reader's position when reading is restarted.

In this way, the events of an application can be followed with perfect
accuracy and without lots of complications. This seems to be an inherently
reliable approach to following the events of an application.

.. code:: python

    # Clean up.
    persistence_policy.close()
