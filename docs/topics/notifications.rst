=============
Notifications
=============

This section discusses how a notification log of the domain events
of an application can be used to update views of the application state.

Other sections in this documentation show how the domain events of an
entity or aggregate are placed in sequence, and projected to obtain
the state of an object. With the library's application domain and
infrastructure layers, it is possible to obtain the state of entity
or aggregate given its ID. But how is the ID obtained?

If a user must sign in using their email address, so long as there is
an up-to-date index of user IDs by email address, the email address can
be resolved to a user ID. To project the application state, we firstly
need a sequence of all the events of the application.

Given a single sequence of events, we need a way to follow them, a way that
can work locally and across a network, and also work regardless of
whether or the update is synchronous or asynchronous.

.. contents:: :local:



Propagating events
------------------

As Vaughn Vernon suggests in his book Implementing Domain Driven Design:

    “at least two mechanisms in a messaging solution must always be consistent with each other: the persistence
    store used by the domain model, and the persistence store backing the messaging infrastructure used to forward
    the Events published by the model. This is required to ensure that when the model’s changes are persisted, Event
    delivery is also guaranteed, and that if an Event is delivered through messaging, it indicates a true situation
    reflected by the model that published it. If either of these is out of lockstep with the other, it will lead to
    incorrect states in one or more interdependent models.”

There are three options, he continues. The first option is to
have the messaging infrastructure and the domain model share
the same persistence store, so changes to the model and
insertion of new messages commit in the same local transaction.
The second option is to have separate datastores for domain
model and messaging but have a two phase commit, or global
transaction, across the two.

The third option is to have the bounded context
control notifications. Vaughn Vernon is his book
Implementing Domain Driven Design relies on the simple logic
of an ascending sequence of integers to allow others to progress
along the event stream.

Timestamps
~~~~~~~~~~

If time itself was ideal, then timestamps would be ideal. Each event
could then have a timestamp that could be used to index and iterate
through the events of the application. However, there are many
clocks, and each runs slightly differently from the other.

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
by using a random component to the timestamp, as with UUID v1, at
the expense of randomizing the order of otherwise simultaneous events.

Such techniques are common, widely discussed, and entirely legitimate approaches
to the complications encountered when using timestamps to sequence events. The big
advantage of using timestamps is that you don't need to generate a sequence of integers,
and applications can be distributed and scaled without performance being limited by a
fragile single-threaded auto-incrementing integer-sequence bottleneck.

In support of this approach, the library's relational record classes for timestamp sequenced items, in
particular the ``TimestampSequencedRecord`` classes for SQLAlchemy and Django, index
their position field, which is a timestamp, and so this index can be used to get all
application events in certain order. Following this sequence will be as reliable as the
timestamps given to the events. So if you use this class in this way, do make sure your
clocks are in sync.

(An improvement to this class could be to have another timestamp field that is populated
by the database server, and index that instead of the application event's timestamp which
would vary according to the variation between the clock of application servers. Code
changes and other suggestions are always welcome.)

Todo: Code example.

Contiguous integers
~~~~~~~~~~~~~~~~~~~

To make propagation perfectly accurate (which is defined here as reproducing the
application's sequence of events perfectly, without any risk of gaps or duplicates
or jumbled items, or race conditions), we can generate and follow a contiguous sequence
of integers. Two such techniques are described below.

The first approach uses the library's relational record managers with integer
sequenced record classes. The ID column of the record class is used to place
all the application's event records in a single sequence. This technique is
recommended for enterprise applications, and the early stages of more ambitious
projects.

Secondly, a much more complicated but possibly more scalable approach uses a
library class called ``BigArray``. This technique accepts downstream
complexity so that capacity is not inherently limited by the technique.
This technique is recommended for parts of mass consumer applications that
need to operate at such a scale that the first approach is restrictive.


Application sequence
--------------------

The fundamental concern is to accomplish perfect accuracy
when propagating the events of an application, so that events are neither
missed, nor duplicated, nor jumbled. The general idea is that once the
sequence of events has been assembled, it can be followed.

In order to update a projection of the application state as a
whole, all the events of the application must have been placed
in a single sequence. We need to be able to follow the sequence
reliably, even as it is being written. We don't want any gaps,
or out-of-order items, or duplicates, or race conditions.

Before continuing to describe the support provided by the library
for sequencing all the events of an application, let's setup an
event store, and a database, needed by the examples below.

Please note, the ``SQLAlchemyRecordManager`` is used with the
``contiguous_record_ids`` option enabled.

.. code:: python

    from eventsourcing.infrastructure.sqlalchemy.manager import SQLAlchemyRecordManager
    from eventsourcing.infrastructure.sqlalchemy.records import StoredEventRecord
    from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemyDatastore, SQLAlchemySettings
    from eventsourcing.infrastructure.eventstore import EventStore
    from eventsourcing.infrastructure.repositories.array import BigArrayRepository
    from eventsourcing.application.policies import PersistencePolicy
    from eventsourcing.infrastructure.sequenceditem import StoredEvent
    from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper

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
    )

    # Setup a sequenced item mapper.
    sequenced_item_mapper = SequencedItemMapper(
        sequenced_item_class=StoredEvent,
    )

    # Setup the event store.
    event_store = EventStore(
        record_manager=record_manager,
        sequenced_item_mapper=sequenced_item_mapper
    )

    # Set up a persistence policy.
    persistence_policy = PersistencePolicy(
        event_store=event_store,
    )

The above infrastructure classes are explained
in other sections of this documentation.

Record managers
~~~~~~~~~~~~~~~

A relational record manager with an integer sequenced record class
can function as an application sequence, especially when using the
``contiguous_record_ids`` option of the library's relational record
managers. This technique ensures that whenever an aggregate command returns
successfully, any events will already have been successfully placed in
both the aggregate's and the application's sequence. This approach provides simplicity and
perfect accuracy, at the cost of an upper limit to rate as with records can be
written: aggregate commands will experience concurrency errors if they attempt to record
events simultaneously with others (in which case they will need to be
retried).

To use this approach, simply use the ``IntegerSequencedRecord`` or the
``StoredEventRecord`` classes with the ``contiguous_record_ids`` constructor
argument of the record manager set to a True value. The ``record_manager``
above was constructed in this way.

.. code:: python

    from eventsourcing.domain.model.entity import VersionedEntity

    all_records = record_manager[:]

    assert len(all_records) == 0, all_records

    first_entity = VersionedEntity.__create__()

    all_records = record_manager[0:5]

    assert len(all_records) == 1, all_records

.. Todo: Change this back to use the all_records() method instead of the [] syntax. Remove the
.. __getitem__ method from the manager (?) class and change the RecordNotificationLog
.. to use the all_records() method instead. The [] feels wrong on the record manager because
.. it isn't obvious whether they it returns sequenced item namedtuples or active record classes
.. and it's good to cope with some more variation in the notification log classes.


BigArray
~~~~~~~~

This is a long section, and can be skipped if you aren't currently
required to scale capacity beyond the capacity of a database table
supported by your infrastructure.

To support ultra-high capacity requirements, the application sequence must
be capable of having a very large number of events, neither swamping
an individual database partition (in Cassandra) nor distributing
things across partitions (or shards) without any particular order so
that iterating through the sequence is slow and expensive. We also want
the application log effectively to have constant time read and write
operations for normal usage.

The library class
:class:`~eventsourcing.domain.model.array.BigArray` satisfies these
requirements quite well, by spanning across many such partitions. It
is a tree of arrays, with a root array
that stores references to the current apex, with an apex that contains
references to arrays, which either contain references to lower arrays
or contain the items assigned to the big array. Each array uses one database
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

That's because the performance of the ``append()`` method is dominated by the
need to walk down the big array's tree of arrays to find the highest assigned
index. Once the index of the next position is known, the item can be assigned
directly to an array.

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
inversely proportional to the array size, since the the larger the array
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
by centralizing the generation of the sequence of integers. Instead of
discovering the next position from the array each time an item is assigned,
an integer sequence generator can be used to generate a contiguous sequence
of integers. This technique eliminates contention around assigning items to
the big array entirely. In consequence, the bandwidth of assigning to a big
array using an integer sequence generator is much greater than using the
``append()`` method.

If the application is executed in only one process, the number generator can
be a simple Python object. The library class
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


Items can be read from the application log using an index or a slice.

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


The application log can be written to by a persistence policy. References
to events can be assigned to the application log before the domain event is
written to the aggregate's own sequence, so that it isn't possible to store
an event in the aggregate's sequence that is not already in the application
log. To do that, construct the application logging policy object before the
normal application persistence policy. Also, make sure the application
log policy excludes the events published by the big array (otherwise there
will be an infinite recursion).

Todo: Code example of policy that places application domain events in a big array.

Commands that fail to write to the aggregate's sequence (due to an operation
error or concurrency error) after the event has been logged in the application log
should probably raise an exception, so that the command is seen to have failed
and so may be retried. This leaves an item in the notification log, but not a
domain event in the aggregate stream (a dangling reference, that may be satisfied later).
If the command failed due to an operational error, the same event maybe
published again, and so it would appear twice in the application log.
And so whilst events in the application log that aren't in the aggregate
sequence can perhaps be ignored by consumers of the application log, care
should be taken to deduplicate events.

If writing the event to its aggregate sequence is successful, then it is
possible to push a notification about the event to a message queue. Failing
to push the notification perhaps should not prevent the command returning
normally. Push notifications could also be generated by another process,
something that pulls from the application log, and pushes notifications
for events that have not already been sent.

(Please note, using the ``BigArray`` class with the Cassandra record
manager requires quite a lot of thought to eliminate all sources of
unreliability. Since it isn't possible to have transactions across
partitions, writing to the aggregate sequence and the application
sequence will happen in different queries, which means events may be
found in the application sequence that are not yet in the aggregate
sequence, and followers will need to decide whether or not the event
will appear in the aggregate sequence. Under these circumstances, it
seems inevitable that the application sequence must be corrected
downstream, adding downstream complexity.)


Notification logs
-----------------

As described in Implementing Domain Driven Design, a notification log
presents a sequence of notification items in linked sections.

Sections are obtained from a notification log using Python's
"square brackets" sequence index syntax. The key is a section ID.
A special section ID called "current" can be used to obtain a section
which contains the latest notification.

Each section contains a limited number items, the size is fixed by
the notification log's ``section_size`` constructor argument. When
the current section is full, it is considered to be an archived section.

All the archived sections have an ID for the next section. Similarly,
all sections except the first have an ID for the previous section.

A client can get the current section, go back until it reaches the
last notification it has already received, and then go forward until
all existing notifications have been received.

The section ID numbering scheme follows Vaughn Vernon's book.
Section IDs are strings: either 'current'; or a string formatted
with two integers separated by a comma. The integers represent
the first and last number of the items included in a section.

The classes below can be used to present a sequence of items,
such the domain events of an application, in linked
sections. They can also be used to present other sequences
for example a projection of the application sequence, where the
events are rendered in a particular way for a particular purpose,
such as analytics.

RecordNotificationLog
~~~~~~~~~~~~~~~~~~~~~

The library class :class:`~eventsourcing.interface.notificationlog.RecordNotificationLog`
is constructed with a relational ``record_manager``, and a ``section_size``.

.. code:: python

    from eventsourcing.interface.notificationlog import RecordNotificationLog

    # Construct notification log.
    notification_log = RecordNotificationLog(record_manager, section_size=5)

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

The sections of the record notification log each have notification items that
reflect the recorded sequenced item.
The items (notifications) in the sections from ``RecordNotificationLog``
are Python dicts with three key-values: ``id``, ``topic``, and ``data``.

The record manager uses its ``sequenced_item_class`` to identify the actual
names of the record fields containing the topic and the data, and constructs
the notifications (the dicts) with the values of those fields. The
notification's data is simple the record data, so if the record data
was encrypted, the notification data will also be encrypted. The keys of
the event record notification are not reflective of the sequence item class.

The ``topic`` value can be resolved to a Python class, such as
a domain event class. An object instance, such as a domain event
object, could then be reconstructed using the notification's ``data``.

In the code below, the function ``resolve_notifications`` shows
how that can be done (this function doesn't exist in the library).

.. code:: python

    def resolve_notifications(notifications):
        return [
            sequenced_item_mapper.from_topic_and_data(
                topic=notification['topic'],
                data=notification['data']
            ) for notification in notifications
        ]

    # Resolve a section of notifications into domain events.
    domain_events = resolve_notifications(section.items)

    # Check we got the first entity's "created" event.
    assert isinstance(domain_events[0], VersionedEntity.Created)
    assert domain_events[0].originator_id == first_entity.id

If the notification data was encrypted by the sequenced item
mapper, the sequence item mapper will decrypt the data before
reconstructing the domain event. In this example, the sequenced
item mapper does not have a cipher, so the notification data is
not encrypted.


BigArrayNotificationLog
~~~~~~~~~~~~~~~~~~~~~~~

Skip this section if you skipped the section about BigArray.

The library class :class:`~eventsourcing.interface.notificationlog.BigArrayNotificationLog`
uses a ``BigArray`` as the application log, and presents its items in linked sections.

.. code:: python

    from eventsourcing.interface.notificationlog import BigArrayNotificationLog

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
just strings ('item0' etc). If the big array were used to sequence the
events of an application, it is possible to assign just the item's sequence
ID and position, and let followers get the actual event.

Remote notification logs
------------------------

The RESTful API design in Implementing Domain Driven Design
suggests a good way to present the notification log, a way that
is simple and can scale using established HTTP technology.

This library has a pair of classes that can help to present a
notification log remotely.

The ``RemoteNotificationLog`` class has the same interface for getting
sections as the local notification log classes described above, but
instead of using a local datasource, it requests serialized
sections from a Web API.

The ``NotificationLogView`` class serializes sections from a local
notification log, and can be used to implement a Web API that presents
notifications to a network.

Alternatively to presenting domain event data and topic information,
a Web API could present only the event's sequence ID and position values,
requiring clients to obtain the domain event from the event store using
those references. If the notification log uses a big array, and the big
array is assigned with only sequence ID and position values, the big array
notification log could be used directly with the ``NotificationLogView``
to notify of domain events by reference rather than by value. However, if
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

The library class :func:`~eventsourcing.interface.notificationlog.NotificationLogView`
presents sections from a local notification log, and can be used to implement a Web API.

The ``NotificationLogView`` class is constructed with a local ``notification_log``
object and an optional ``json_encoder_class`` (which defaults to the library's.
``ObjectJSONEncoder`` class, used explicitly in the example below).

The example below uses the record notification log, constructed above.

.. code:: python

    import json

    from eventsourcing.interface.notificationlog import NotificationLogView
    from eventsourcing.utils.transcoding import ObjectJSONEncoder, ObjectJSONDecoder

    view = NotificationLogView(
        notification_log=notification_log,
        json_encoder_class=ObjectJSONEncoder
    )

    section_json, is_archived = view.present_section('1,5')

    section_dict = json.loads(section_json, cls=ObjectJSONDecoder)

    assert section_dict['section_id'] == '1,5'
    assert section_dict['next_id'] == '6,10'
    assert section_dict['previous_id'] == None
    assert section_dict['items'] == notification_log['1,5'].items
    assert len(section_dict['items']) == 5

    item = section_dict['items'][0]
    assert item['id'] == 1
    assert '__event_hash__' in item['data']
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


A Web application could identify a section ID from an HTTP request
path, and respond by returning an HTTP response with JSON
content that represents that section of a notification log.

The example below uses the notification log from the
example above.

.. code:: python

    def notification_log_wsgi(environ, start_response):

        # Identify section from request.
        section_id = environ['PATH_INFO'].strip('/')

        # Construct notification log view.
        view = NotificationLogView(notification_log)

        # Get serialized section.
        section, is_archived = view.present_section(section_id)

        # Start HTTP response.
        status = '200 OK'
        headers = [('Content-type', 'text/plain; charset=utf-8')]
        start_response(status, headers)

        # Return body.
        return [(line + '\n').encode('utf8') for line in section.split('\n')]

A more sophisticated application might include
an ETag header when responding with the current section, and
a Cache-Control header when responding with archived sections.


RemoteNotificationLog
~~~~~~~~~~~~~~~~~~~~~

The library class :class:`~eventsourcing.interface.notificationlog.RemoteNotificationLog`
can be used in the same way as the local notification logs above. The difference is that
rather than accessing a database using a ``BigArray`` or record manager, it makes requests
to an API.

The ``RemoteNotificationLog`` class is constructed with a ``base_url``, a ``notification_log_id``
and a ``json_decoder_class``. The JSON decoder must be capable of decoding JSON encoded by
the API. Hence, the JSON decoder must match the JSON encoder used by the API.

The default ``json_decoder_class`` is the library's ``ObjectJSONDecoder``. This encoder
matches the default ``json_encoder_class`` of the library's ``NotificationLogView`` class,
which is the library's ``ObjectJSONEncoder`` class. If you want to extend the JSON encoder
classes used here, just make sure they match, otherwise you will get decoding errors.

The ``NotificationLogReader`` can use the ``RemoteNotificationLog`` in the same way that
it uses a local notification log object. Just construct it with a remote notification log
object, rather than a local notification log object, then read notifications in the same
way (as described above).

If the API uses a ``NotificationLogView`` to serialise the sections of a local
notification log, the remote notification log object functions effectively as a
proxy for a local notification log on a remote node.

.. code:: python

    from eventsourcing.interface.notificationlog import RemoteNotificationLog

    remote_notification_log = RemoteNotificationLog("base_url")

If a server were running at "base_url" the ``remote_notification_log`` would
function in the same was as the local notification logs described above, returning
section objects for section IDs using the square brackets syntax.

If the section objects were created by a ``NotifcationLogView`` that
had the ``notification_log`` above, we could obtain all the events of an
application across an HTTP connection, accurately and without great
complication.

See ``test_notificationlog.py`` for an example that uses a Flask app running
in a local HTTP server to get notifications remotely using these classes.


Notification log reader
-----------------------

The library object class
:class:`~eventsourcing.interface.notificationlog.NotificationLogReader` effectively
functions as an iterator, yielding a continuous sequence of notifications that
it discovers from the sections of a notification log (local or remote).

A notification log reader object will navigate the linked sections of a notification
log, backwards from the "current" section of the notification log, until reaching the position
it seeks. The position, which defaults to ``0``, can be set directly with the reader's ``seek()``
method. Hence, by default, the reader will navigate all the way back to the
first section.

After reaching the position it seeks, the reader will then navigate forwards, yielding
as a continuous sequence all the subsequent notifications in the notification log.

As it navigates forwards, yielding notifications, it maintains position so that it can
continue when there are further notifications. This position could be persisted, so that
position is maintained across invocations, but that is not a feature of the
``NotificationLogReader`` class, and would have to be added in a subclass or client object.

The ``NotificationLogReader`` supports slices. The position is set indirectly when a slice
has a start index.

All the notification logs discussed above (local and remote) have the same interface,
and can be used by ``NotificationLogReader`` progressively to obtain unseen notifications.

The example below happens to yield notifications from a big array notification log, but it
would work equally well with a record notification log, or with a remote notification log.

Todo: Maybe just use "obj.read()" rather than "list(obj)", so it's more file-like.

.. code:: python

    from eventsourcing.interface.notificationlog import NotificationLogReader

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
    all_notifications = reader.read()
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
    subsequent_notifications = reader.read()
    assert len(subsequent_notifications) == 2

    # Check the position has advanced.
    assert reader.position == 11

    # Read all subsequent notifications (should be none).
    subsequent_notifications = reader.read()
    len(subsequent_notifications) == 0

    # Publish three more events.
    VersionedEntity.__create__()
    VersionedEntity.__create__()
    last_entity = VersionedEntity.__create__()

    # Read all subsequent notifications (should be three).
    subsequent_notifications = reader.read()
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
    subsequent_notifications = reader.read()
    assert subsequent_notifications == []

    # Check the position has advanced.
    assert reader.position == 14

The position could be persisted, and the persisted value could be
used to initialise the reader's position when reading is restarted.

In this way, the events of an application can be followed with perfect
accuracy and without lots of complications. This seems to be an inherently
reliable approach to following the events of an application.


Updating projections
--------------------

Once the events of an application can be followed reliably,
they can be used to update projections of the application state.

Synchronous update
~~~~~~~~~~~~~~~~~~

You may wish to update a view of an aggregate synchronously
whenever an event is published. You may wish simply to
subscribe to the events of the aggregate. Then, whenever
an event occurs, the projection can be updated.

The library decorator function
:func:`~eventsourcing.domain.model.decorators.subscribe_to`
can be used for this purpose.

The most simple implementation of a projection would consume
an event synchronously as it is published by updating the
view without considering whether the event was a duplicate
or previous events were missed. This may be perfectly adequate
for projecting events that are by design independent, such as
tracking all 'Created' events so the extent aggregate IDs are
available in a view.

It is also possible for a synchronous update to refer to an application
log and catch up if necessary, perhaps after an error or because
the projection is new to the application and needs to initialise.

Of course, it is possible to access aggregates and other views when
updating a view, especially to avoid bloating events with redundant
information that might be added to avoid such queries.

.. code::

    @subscribe_to(Todo.Created)
    def new_todo_projection(event):
        todo = TodoProjection(id=event.originator_id, title=event.title)
        todo.save()


Todo: Code example showing "Projection" class using a notification log
reader and (somehow) stateful position in the log, to follow application
events and update a view.

The view model could be saved as a normal record, or stored in
a sequence that follows the event originator version numbers, perhaps
as snapshots, so that concurrent handling of events will not lead to a
later state being overwritten by an earlier state. Older versions of
the view could be deleted later.

If the view somehow fails to update after the domain event has been stored,
then the view will become inconsistent. Since it is not desirable
to delete the event once it has been stored, the command must return
normally despite the view update failing, so that the command
is not retried. The failure to update will need to be logged, or
otherwise handled, in a similar way to failures of asynchronous updates.

It is possible to use the decorator in a downstream application, in
which domain events are republished following the application
sequence asynchronously. The decorator would be called synchronously with the
republishing of the event. In this case, if the view update routine somehow
fails to update, the position of the downstream application in the upstream
sequence would not advance until the view is restored to working order, after
which the view will be updated as if there had been no failure.


Asynchronous update
~~~~~~~~~~~~~~~~~~~

Updates can be triggered by pushing notifications to
messaging infrastructure, and having the remote components subscribe.
De-duplication would involve tracking which events have already
been received.

To keep the messaging infrastructure stable, it may be sufficient
simply to identify the domain event, perhaps with its sequence ID
and position.

If anything goes wrong with messaging infrastructure, such that a
notification is sent but not received, remote components can detect
they have missed a notification and pull the notifications they have
missed. A pull mechanism, such as that described above, can be used to
catch up.

The same mechanism can be used when materialized views (or other kinds
of projections) are developed after the application has been initially
deployed and require initialising from an established application
sequence, or after changes need to be reinitialised from scratch, or
updated after being offline for some reason.

Todo: Something about pumping events to a message bus, following
the application sequence.

Todo: Something about republishing events in a downstream application
that has subscribers such as the decorator above. Gives opportunity for
sequence to be reconstructed in the application before being published
(but then what if several views are updated and the last one fails?
are they all updated in the same a transaction, are do they each maintain
their own position in the sequence, or does the application just have one
subscriber and one view?)

Todo: So something for a view to maintain its position in the sequence,
perhaps version the view updates (event sourced or snapshots) if there
are no transactions, or use a dedicated table if there are transactions.

.. code:: python

    # Clean up.
    persistence_policy.close()


.. Todo: Pulling from remote notification log.

.. Todo: Publishing and subscribing to remote notification log.

.. Todo: Deduplicating domain events in receiving context.
.. Events may appear twice in the notification log if there is
.. contention over the command that generates the logged event,
.. or if the event cannot be appended to the aggregate stream
.. for whatever reason and then the command is retried successfully.
.. So events need to be deduplicated. One approach is to have a
.. UUID5 namespace for received events, and use concurrency control
.. to make sure each event is acted on only once. That leads to the
.. question of when to insert the event, before or after it is
.. successfully applied to the context? If before, and the event
.. is not successfully applied, then the event maybe lost. Does
.. the context need to apply the events in order?
.. It may help to to construct a sequenced command log, also using
.. a big array, so that the command sequence can be constructed in a
.. distributed manner. The command sequence can then be executed in
.. a distributed manner. This approach would support creating another
.. application log that is entirely correct.

.. Todo: Race conditions around reading events being assigned using
.. central integer sequence generator, could potentially read when a
.. later index has been assigned but a previous one has not yet been
.. assigned. Reading the previous as None, when it just being assigned
.. is an error. So perhaps something can wait until previous has
.. been assigned, or until it can safely be assumed the integer was lost.
.. If an item is None, perhaps the notification log could stall for
.. a moment before yielding the item, to allow time for the race condition
.. to pass. Perhaps it should only do it when the item has been assigned
.. recently (timestamp of the ItemAdded event could be checked) or when
.. there have been lots of event since (the highest assigned index could
.. be checked). A permanent None value should be something that occurs
.. very rarely, when an issued integer is not followed by a successful
.. assignment to the big array. A permanent "None" will exist in the
.. sequence if an integer is lost perhaps due to a database operation
.. error that somehow still failed after many retries, or because the
.. client process crashed before the database operation could be executed
.. but after the integer had been issued, so the integer became lost.
.. This needs code.

.. Todo: Automatic initialisation of the integer sequence generator RedisIncr
.. from getting highest assigned index. Or perhaps automatic update with
.. the current highest assigned index if there continues to be contention
.. after a number of increments, indicating the issued values are far behind.
.. If processes all reset the value whilst they are also incrementing it, then
.. there will be a few concurrency errors, but it should level out quickly.
.. This also needs code.

.. Todo: Use actual domain event objects, and log references to them. Have an
.. iterator that returns actual domain events, rather than the logged references.
.. Could log the domain events, but their variable size makes the application log
.. less stable (predictable) in its usage of database partitions. Perhaps
.. deferencing to real domain events could be an option of the notification log?
.. Perhaps something could encapsulate the notification log and generate domain
.. events?

.. Todo: Configuration of remote reader, to allow URL to be completely configurable.
