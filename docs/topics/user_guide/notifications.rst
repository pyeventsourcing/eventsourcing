=============================
Projections and notifications
=============================

Synchronous update
------------------

In a simple situation, you may wish to update a projection of
an aggregate synchronously when it changes. If a projection
depends only on one aggregate, you may wish simply to subscribe
to the events of the aggregate. Then, whenever an event occurs,
the projection can be updated.

The library has a decorator function
:func:`~eventsourcing.domain.model.decorators.subscribe_to`
that can be used for this purpose.

.. code::

    @subscribe_to(Todo.Created)
    def new_todo_projection(event):
        todo = TodoProjection(id=event.originator_id, title=event.title)
        todo.save()

The projection could be a normal record, or stored in a sequence
that follows the originator version numbers, so that concurrent
handling of events will not lead to a later state being overwritten
by an earlier state. Older versions of the view could be deleted later.

If the view fails to update after the event has been stored,
then the view will be inconsistent with the latest state
of the aggregate. Since it is not desirable to delete the
event once it has been stored, the command must return
normally despite the view update failing, so that the command
is not retried.

Without further refinements, such as with "round
robin" polling of the known aggregates, the view will
only be updated next time the aggregate changes.
Event if a "round robin" approach was taken, if the first
event of an aggregate is not applied to a projection, there
is no way for it to know that aggregate exists, and so cannot
possibly check for updates to that aggregate.

This last concern brings us to needing a single application log
that sequences all events of the application.


Asynchronous update
-------------------

Asynchronous updates can be used to update other aggregates,
especially aggregates in a remote context.

The fundamental concern is to accomplish high fidelity when
propagating a stream of events, so that events are neither
missed nor are they duplicated. As Vaughn Vernon suggests
in his book Implementing Domain Driven Design:

    “at least two mechanisms in a messaging solution must always be consistent with each other: the persistence
    store used by the domain model, and the persistence store backing the messaging infrastructure used to forward
    the Events published by the model. This is required to ensure that when the model’s changes are persisted, Event
    delivery is also guaranteed, and that if an Event is delivered through messaging, it indicates a true situation
    reflected by the model that published it. If either of these is out of lockstep with the other, it will lead to
    incorrect states in one or more interdependent models.”


There are three options. The first option is to have the
messaging infrastructure and the domain model share the same
persistence store, so changes to the model and insertion of
new messages commit in the same local transaction.
The second option is to have separate datastores for domain
model and messaging but have a two phase commit, or global
transaction, across the two.

The third option is to have the bounded context
control notifications. It is the third approach that is taken here.
The approach taken by Vaughn Vernon is his book Implementing Domain
Driven Design is to rely on the simple logic of an ascending sequence
of integers to allow others to progress along the event stream.

A pull mechanism that allows others to pull events that they
don't yet have can be used to allow remote components to catch
up. The same mechanism can be used if the remote component is developed
after the application has been deployed and so requires initialising
from an established application stream, or otherwise needs to be
reconstructed from scratch.

Updates can be triggered by pushing the notifications to
messaging infrastructure, and having the remote components subscribe.
If anything goes wrong with messaging infrastructure, such that a
notification is not received, remote components can fall back onto
pulling notifications they have missed.


Application log
---------------

In order to update a projection of more than one aggregate, or of
the application state as a whole, we need a single sequence
to log all the events of the application.

The application log needs to be a single sequence, that can be generated
without error in a multi-threaded application. We want a log that follows
an increasing sequence of integers. The application log must also be capable
of storing a very large sequence of events, neither swamping an individual
database partition nor scattering things across partitions without order so
that iterating through the sequence is slow and expensive.
We also want the application log effectively to have constant time read and
write operations. The library class
:class:`~eventsourcing.domain.model.array.BigArray` satisfies these
requirements quite well.

Items can be appended to a big array using the ``append()`` method.
The append() method identifies the next available index in the array,
and then assigns the item to that index in the array.

The performance of the ``append()`` method is proportional to the log of the
index in the array, to the base of the array size used in the big array, rounded
up to the nearest integer, plus one. For example, if the array size is 10000, then it
will take only 50% longer to append the 100,000,000th item to the big array than the
1st one. By the time the 1,000,000,000,000th index is appended to a big array, the
``append()`` method will take only twice as long as the 1st.

.. code:: python

    from uuid import uuid4
    from eventsourcing.domain.model.array import BigArray, ItemAssigned
    from eventsourcing.infrastructure.sqlalchemy.activerecords import SQLAlchemyActiveRecordStrategy
    from eventsourcing.infrastructure.sqlalchemy.activerecords import StoredEventRecord
    from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemyDatastore, SQLAlchemySettings
    from eventsourcing.infrastructure.eventstore import EventStore
    from eventsourcing.infrastructure.repositories.array import BigArrayRepository
    from eventsourcing.application.policies import PersistencePolicy
    from eventsourcing.infrastructure.sequenceditem import StoredEvent
    from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper


    datastore = SQLAlchemyDatastore(
        settings=SQLAlchemySettings(),
        tables=[StoredEventRecord],
    )
    datastore.setup_connection()
    datastore.setup_tables()

    event_store = EventStore(
            active_record_strategy=SQLAlchemyActiveRecordStrategy(
                session=datastore.session,
                active_record_class=StoredEventRecord,
                sequenced_item_class=StoredEvent,
            ),
            sequenced_item_mapper=SequencedItemMapper(
                sequenced_item_class=StoredEvent,
            )
        )
    persistence_policy = PersistencePolicy(
        event_store=event_store,
        event_type=ItemAssigned,
    )

    array_id = uuid4()

    repo = BigArrayRepository(
        event_store=event_store,
        array_size=10000
    )

    application_log = repo[array_id]
    application_log.append('event0')
    application_log.append('event1')
    application_log.append('event2')
    application_log.append('event3')


Because there is a small duration of time between checking for the next
position and using it, another thread could jump in and use the position
first. If that happens, a :class:`~eventsourcing.exceptions.ConcurrencyError`
will be raised by the :class:`~eventsourcing.domain.model.array.BigArray`
object. In such a case, another attempt can be made to append the item.

Items can be assigned directly. If an item has already been assigned,
a concurrency error will be raised. Items cannot be unassigned, each index
can only be used once.

The average performance of assigning an item is a constant time. The worst
case is log of the index with base array size, which occurs when containing
arrays are added, so that the last highest assigned index can be discovered.
The probability of departing from average performance is inversely proportional
to the array size, since the the larger the array size, the less often the base
arrays fill up.

.. code:: python

    from eventsourcing.exceptions import ConcurrencyError

    assert application_log.get_next_position() == 4

    application_log[4] = 'event4'
    try:
        application_log[4] = 'event4a'
    except ConcurrencyError:
        pass
    else:
        raise


If the next available position in the array must be identified
each time an item is assigned, the amount of contention will increase
as the number of threads increases. Using the ``append()`` method alone
will be perfectly alright if the time period of appending events is greater
than the time it takes to identify the next available index and assign to
it. At that rate, contention will not lead to congestion. Different nodes
can take their chances assigning to what they believe is an unassigned
index, and if another has already taken that position, the attempt can
be retried.

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

If the application has only one process, the number generator can
be a simple Python generator. The library class
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


An integer sequence generator can be used when assigning items to the
application log.

.. code:: python

    application_log[next(integers)] = 'event5'
    application_log[next(integers)] = 'event6'

    assert application_log.get_next_position() == 7


Items can be read from the application log using an index or a slice.

The performance of reading an item at a given index is always constant time
with respect to the number of the index. The base array ID, and the index of
the item in the base array, can be calculated from the number of the index.

The performance of reading a slice of items it proportional to the
size of the slice. Consecutive items in a base array are stored consecutively
in the same database partition, and if the slice overlaps more than base
array, the iteration proceeds to the next partition.

.. code:: python

    assert application_log[0] == 'event0'
    assert list(application_log[5:7]) == ['event5', 'event6']


The application log can be written to by a persistence policy. References
to events can be assigned to the application log before the domain event is
written to the aggregate's own sequence, so that it isn't possible to store
an event in the aggregate's sequence that is not already in the application
log.

Commands that fail to write to the aggregate's sequence after the event
has been logged in the application's sequence should raise an exception, so
that the command is known to have failed and may be retried. Events in the
application log that aren't in the aggregate sequence can be ignored.

If writing the event to its aggregate sequence is successful, then it is
possible to push a notification about the event to a message queue. Failing
to push the notification perhaps should not prevent the command returning
normally. Push notifications could also be generated by a different process,
that pulls from the application log, and pushes notifications for events
that have not already been sent.


Notification log
----------------

As described in Implementing Domain Driven Design, a notification log
is presented in linked sections. The "current section" is returned by
default, and contains the very latest notification and some of the
preceding notifications. There are also archived sections that
contain all the earlier notifications. When the current section is
full, it is considered to be an archived section that links to the new
current section.

Readers can navigate the linked sections from the current section backwards
until the archived section is reached that contains the last notification
seen by the client. If the client has not yet seen any notifications, it will
navigate back to the first section. Readers can then navigate forwards, revealing
all existing notifications that have not yet been seen.

The library class :class:`~eventsourcing.interface.notificationlog.NotificationLog`
encapsulates the application log and presents linked sections. The library class
:class:`~eventsourcing.interface.notificationlog.NotificationLogReader` is an iterator
that yields notifications. It navigates the sections of the notification log, and
maintains position so that it can continue when there are further notifications.
The position can be set directly with the ``seek()`` method. The position is set
indirectly when a slice is taken with a start index. The position is set to zero
when the reader is constructed.

.. code:: python

    from eventsourcing.interface.notificationlog import NotificationLog, NotificationLogReader

    # Construct notification log.
    notification_log = NotificationLog(application_log, section_size=10)

    # Get the "current "section from the notification log (numbering follows Vaughn Vernon's book)
    section = notification_log['current']
    assert section.section_id == '1,10'
    assert len(section.items) == 7, section.items
    assert section.previous_id == None
    assert section.next_id == None

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
    all_notifications = list(reader)
    assert all_notifications == ['event0', 'event1', 'event2', 'event3', 'event4', 'event5', 'event6']

    # Check the position has advanced.
    assert reader.position == 7

    # Read all subsequent notifications (should be none).
    subsequent_notifications = list(reader)
    assert subsequent_notifications == []

    # Assign more events to the application log.
    application_log[next(integers)] = 'event7'
    application_log[next(integers)] = 'event8'

    # Read all subsequent notifications (should be two).
    subsequent_notifications = list(reader)
    assert subsequent_notifications == ['event7', 'event8']

    # Check the position has advanced.
    assert reader.position == 9

    # Read all subsequent notifications (should be none).
    subsequent_notifications = list(reader)
    assert subsequent_notifications == []

    # Assign more events to the application log.
    application_log[next(integers)] = 'event9'
    application_log[next(integers)] = 'event10'
    application_log[next(integers)] = 'event11'

    # Read all subsequent notifications (should be two).
    subsequent_notifications = list(reader)
    assert subsequent_notifications == ['event9', 'event10', 'event11']

    # Check the position has advanced.
    assert reader.position == 12

    # Read all subsequent notifications (should be none).
    subsequent_notifications = list(reader)
    assert subsequent_notifications == []

    # Get the "current "section from the notification log (numbering follows Vaughn Vernon's book)
    section = notification_log['current']
    assert section.section_id == '11,20'
    assert section.previous_id == '1,10'
    assert section.next_id == None
    assert len(section.items) == 2, len(section.items)

    # Get the first section from the notification log (numbering follows Vaughn Vernon's book)
    section = notification_log['1,10']
    assert section.section_id == '1,10'
    assert section.previous_id == None
    assert section.next_id == '11,20'
    assert len(section.items) == 10, section.items


The RESTful API design in Implementing Domain Driven Design
suggests a good way to present the notification log, a way that
is simple and can scale using established HTTP technology.

The library function :func:`~eventsourcing.interface.notificationlog.present_section`
serializes sections from the notification log for use in a view.

A Web application view can pick out from the request path the notification
log ID and the section ID, and return an HTTP response with the JSON content
that results from calling :func:`~eventsourcing.interface.notificationlog.present_section`.

The library class :class:`~eventsourcing.interface.notificationlog.RemoteNotificationLog`
issues HTTP requests to a RESTful API that presents sections from the notification log.
It has the same interface as :class:`~eventsourcing.interface.notificationlog.NotificationLog`
and so can be used by :class:`~eventsourcing.interface.notificationlog.NotificationLogReader`
progressively to obtain unseen notifications.

Todo: Pulling from remote notification log.

Todo: Publishing and subscribing to remote notification log.

Todo: Deduplicating domain events in receiving context.


Events may appear twice in the notification log if there is
contention over the command that generates the logged event,
or if the event cannot be appended to the aggregate stream
for whatever reason and then the command is retried successfully.
So events need to be deduplicated. One approach is to have a
UUID5 namespace for received events, and use concurrency control
to make sure each event is acted on only once. It may help to
to construct a sequenced command log, also using a big array, so
that the command sequence can be constructed in a distributed manner.
The command sequence can then be executed in a controlled manner.

Todo: Race conditions around reading events being assigned using
central integer sequence generator, could potentially read when a
later item has been assigned but a previous one has not yet been
assigned. So perhaps something can wait until previous has been
assigned, or until it can safely be assumed the integer was lost.
If an item is None, perhaps the notification log could stall for
a moment before yielding the item, to allow time for the race condition
to pass. Perhaps it should only do it when the item has been assigned
recently (timestamp of the ItemAdded event could be checked) or when
there have been lots of event since (the highest assigned index could
be checked). A permanent None value should be something that occurs
very rarely, when an issued integer is not followed by a successful
assignment to the big array. A permanent "None" will exist in the
sequence if an integer is lost perhaps due to a database operation
error that somehow still failed after many retries, or because the
client process crashed before the database operation could be executed
but after the integer had been issued, so the integer became lost.
This needs code.

Todo: Automatic initialisation of the integer sequence generator RedisIncr
from getting highest assigned index. Or perhaps automatic update with
the current highest assigned index if there continues to be contention
after a number of increments, indicating the issued values are far behind.
If processes all reset the value whilst they are also incrementing it, then
there will be a few concurrency errors, but it should level out quickly.
This also needs code.
