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
So if the first event of an aggregate is not applied to a
projection, there is no way for it to know that aggregate
exists, and so cannot possibly check for updates to that aggregate.

This last concern brings us to needing a single application log
that sequences all events of the application.

Application log
---------------

In order to update a projection of more than one aggregate, or of
the application state as a whole, we need a single sequence
for all the events of the application.

An application in a remote context can pull items from the application
log added after a particular position, so that an object can be updated
asynchronously. It can also subscribe to push notifications.

Writing an application log brings its own difficulties, in particular
how to generate a single sequence in a multi-threaded application? and
how to store a large sequence of events without either swamping one
partition in a database or distributing things across partitions so
much that iterating through the sequence is slow and expensive? The
library class :class:`~eventsourcing.domain.model.array.BigArray` provides
a solution to these concerns, by constructing a tree of sequences each
in their own partition.

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

    repo = BigArrayRepository(event_store=event_store)

    application_log = repo[array_id]
    application_log.append('event0')
    application_log.append('event1')
    application_log.append('event2')
    application_log.append('event3')

Items can be assigned directly. The append() method just
gets the next available position in the array, and then assigns
the item to that position in the array. Because there is a small
time duration between checking for the next position and using it,
another thread could jump in and use the position first. If that
happens, a :class:`~eventsourcing.exceptions.ConcurrencyError` will
be raised by the :class:`~eventsourcing.domain.model.array.BigArray`
object. In such a case, another attempt can be made to append the item.

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


If each thread must independently discover the next available
position in the array each time an item is assigned, as the
number of threads increases, so will the amount of contention,
and the number of assignments to the array will increase.

Instead of discovering the next position from the array
each time an item is assigned, a number generator can be used to
generate a sequence of integers. If the application has only one
process, the number generator can be a simple Python generator.

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

If the application is deployed across many nodes, a number
generator service can be used. The library has class
:class:`~eventsourcing.infrastructure.integersequencegenerators.redisincr.RedisIncr`
which uses Redis' INCR command to generate a contiguous sequence of integers
that can be shared across multiple processes.

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
big array.

.. code:: python

    application_log[next(integers)] = 'event5'
    application_log[next(integers)] = 'event6'

    assert application_log.get_next_position() == 7

    assert application_log[0] == 'event0'
    assert list(application_log[5:7]) == ['event5', 'event6']


The application log can be used in an entity persistence policy, and
can be assigned to before the domain event is written to the aggregate's
own sequence, so that it isn't possible to store an event in the aggregate's
sequence that is not already in the application log. Commands
that fail to write to the aggregate's sequence after the event has been
logged in the application's sequence should raise an exception, so
that the command may be retried. Events in the
application log that aren't in the aggregate sequence can be
ignored.

If writing to aggregate sequence is successful, then it is possible
to push a notification about the event to a message queue. Failing
to push the notification perhaps should not prevent the command returning
normally. Push notifications could also be generated by a different process,
that pulls from the application log, and pushes notifications for events
that have not already been sent.

The notifications can be used to retrieve the domain events, and the
domain events can be deduplicated.

Asynchronous update
-------------------

Asynchronous updates can be used to update other aggregates,
especially aggregates in another bounded context.

The fundamental concern is to accomplish high fidelity when
propagating a stream of events, so that events are neither
missed nor are they duplicated. As Vaughn Vernon suggests
in his book Implementing Domain Driven Design:

    “at least two mechanisms in a messaging solution must always be consistent with each other: the persistence store used by the domain model, and the persistence store backing the messaging infrastructure used to forward the Events published by the model. This is required to ensure that when the model’s changes are persisted, Event delivery is also guaranteed, and that if an Event is delivered through messaging, it indicates a true situation reflected by the model that published it. If either of these is out of lockstep with the other, it will lead to incorrect states in one or more interdependent models.”

He gives three options. The first option is to have the
messaging infrastructure and the domain model share the same
persistence store, so changes to the model and insertion of
new messages happen commit in the same local transaction.
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
from an established application stream, or otherwise need to be
reconstructed from scratch.

Updates can be triggered by pushing the notifications to
messaging infrastructure, and having the remote components subscribe.
If anything goes wrong with messaging infrastructure, such that a
notification is not received, remote components can fall back onto
pulling notifications they have missed.

This implies a log that spans all the aggregates in the originating
context, and in the receiving context something to track the position
of the last notification that was applied. We want a log that
follows an incrementing integer sequence. We want a log that has
constant time read and write operations. We want the log effectively
to have infinite capacity, so it isn't at risk of becoming full, and
so we want to distribute the log across multiple partitions. The library
class :class:`~eventsourcing.domain.model.array.BigArray` has been
designed for this purpose, and can be used to log references to all
the events in a bounded context.

Messages can be sent when an event is successfully stored. Or an
out-of-band process can pull from the notification log and push
notifications, as if the messaging infrastructure were its projected view.


Notification log
----------------

As described in Implementing Domain Driven Design, the application log
can be presented as a notification log, in linked sections. There is a
current section that contains the latest notification and some of the
preceding notifications, and archived sections that contain all the
earlier notifications. When the current section is full, it is considered
to be an archived section that links to the new current section.

Readers can navigate the linked sections from the current section backwards
until the archived section is reached that contains the last notification
seen by the client. If the client has not yet seen any notification, it will
navigate to the first section. Readers can then navigate forwards, yielding
all existing notifications that have not yet been seen.

The library class :class:`~eventsourcing.interface.notificationlog.LocalNotificationLog`
encapsulates the application log and presents linked sections. The library class
:class:`~eventsourcing.interface.notificationlog.NotificationLogReader` is an iterator
that yields notifications. It navigates the sections of the notification logand, optionally
with a slice from the position of the last seen notification.

.. code:: python

    from eventsourcing.interface.notificationlog import LocalNotificationLog, NotificationLogReader

    notification_log = LocalNotificationLog(
        big_array=application_log,
        section_size=10,
    )

    reader = NotificationLogReader(notification_log)

    all_notifications = list(reader)

    assert all_notifications == ['event0', 'event1', 'event2', 'event3', 'event4', 'event5', 'event6']

    position = len(all_notifications)

    subsequent_notifications = list(reader[position:])
    assert subsequent_notifications == []

    application_log[next(integers)] = 'event7'
    application_log[next(integers)] = 'event8'

    subsequent_notifications = list(reader[position:])
    position += len(subsequent_notifications)
    assert subsequent_notifications == ['event7', 'event8']

    assert position == 9

    subsequent_notifications = list(reader[position:])
    assert subsequent_notifications == []
    position += len(subsequent_notifications)

    application_log[next(integers)] = 'event9'
    application_log[next(integers)] = 'event10'
    application_log[next(integers)] = 'event11'

    subsequent_notifications = list(reader[position:])
    assert subsequent_notifications == ['event9', 'event10', 'event11']
    position += len(subsequent_notifications)

    assert position == 12


The RESTful API design in Implementing Domain Driven Design
suggests a good way to present the application log, a way that
is simple and can scale using established HTTP technology.

The library class :class:`~eventsourcing.interface.notificationlog.RemoteNotificationLog`
issues HTTP requests to a RESTful API that hopefully presents sections from the notification
log. The library function :func:`~eventsourcing.interface.notificationlog.present_section`
serializes sections from the notification log for use in a view. The view just needs to pick
out from the request URL the notification log ID and the section ID, and return
an HTTP response with the JSON content that results from calling
:func:`~eventsourcing.interface.notificationlog.present_section`.

Todo: Pulling from remote notification log.

Todo: Publishing and subscribing to notification log.

Todo: Following notification log and deduplicating the domain events.

Todo: Sending deduplicated domain events to messaging infrastructure.
