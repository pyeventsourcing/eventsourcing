===========
Projections
===========

This section describes projecting domain events.

Projections can be updated synchronously by direct event subscription, or
asynchronously by following notification logs. Notifications can be pulled,
and pulling can be driven by subscribing to events.

.. contents:: :local:


Subscribing to events
---------------------

The library function
:func:`~eventsourcing.domain.model.decorators.subscribe_to`
can be used to decorate functions, so that the function is called
each time a matching event is published by the library's pub-sub mechanism.

The example below, which is incomplete because the ``TodoView`` is not
defined, suggests that record ``TodoView`` can be created whenever a
``Todo.Created`` event is published. Perhaps there's a ``TodoView`` table
with an index of todo titles, or perhaps it can be joined with a table of users.

.. code:: python

    from eventsourcing.domain.model.decorators import subscribe_to
    from eventsourcing.domain.model.entity import DomainEntity


    class Todo(DomainEntity):
        class Created(DomainEntity.Created):
            pass

    @subscribe_to(Todo.Created)
    def new_todo_projection(event):
        todo = TodoView(id=event.originator_id, title=event.title, user_id=event.user_id)
        todo.save()

It is possible to access aggregates and other views when
updating a view, especially to avoid bloating events with redundant
information that might be added to avoid such queries. Transactions
can be used to insert related records, building a model for a view.

It is possible to use the decorator in a downstream application which
republishes domain events perhaps published by an original application
that uses messaging infrastructure such as an AMQP system. The decorated
function would be called synchronously with the republishing of the event,
but asynchronously with respect to the original application.

A naive projection might consume events as they are published
and update the projection without considering whether the event
was a duplicate, or if previous events were missed.
The trouble with this approach is that, without further modification, without
referring to a fixed sequence and maintaining position in that sequence, there
is no way to recover when events have been missed. If the projection somehow
fails to update when an event is received, then the event will be lost forever to
the projection, and the projection will be forever inconsistent.

Of course, it is possible to follow a fixed sequence of events, for example
using notification logs.


Reading notification logs
-------------------------

If the events of an application are presented as a sequence of
notifications, then the events can be projected using a notification
reader to pull unseen items.

Getting new items can be triggered by pushing prompts to e.g. an AMQP
messaging system, and having the remote components handle the prompts
by pulling the new notifications. To minimise load on the messaging
infrastructure, it may be sufficient simply to send an empty message,
and thereby prompt receivers into pulling new notifications. This may
reduce latency or avoid excessive polling for updates, but the benefit
would be obtained at the cost of additional complexity. Prompts
that include the position of the notification in its sequence would
allow a follower to know when it is being prompted about notifications
it already pulled, and could then skip the pulling operation.

Examples
--------

Application state replication
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Using event record notifications, the state of an application can be
replicated perfectly. If an application can present its event records
as a notification log, then a "replicator" can read the notification
log and write copies of the original records into a replica's record
manager. (If the original application could be partitioned, with each
partition having its own notification log, then the partitions could
be replicated concurrently, which would allow scaling by application
partition. Partitioning an application isn't currently supported in
the library.)

In the example below, the ``SimpleApplication`` class is used, which
has a ``RecordManagerNotificationLog`` as its ``notification_log``.
Reading this log, locally or remotely, will yield all the event records
persisted by the ``SimpleApplication``. The ``SimpleApplication``
uses a record manager with contiguous record IDs which allows it to
be used within a record manager notification log object.

A record manager notification log object represents records as record
notifications. With record notifications, the ID of the record in the
notification is used to place the notification in its sequence.
Therefore the ID of the last replicated record is used to determine
the current position in the original application's notification log,
which gives "exactly once" processing.

.. code:: python

    from eventsourcing.application.simple import SimpleApplication
    from eventsourcing.exceptions import ConcurrencyError
    from eventsourcing.domain.model.aggregate import AggregateRoot
    from eventsourcing.interface.notificationlog import NotificationLogReader, RecordManagerNotificationLog


    # Define record replicator.
    class RecordReplicator(object):
        def __init__(self, notification_log, record_manager):
            self.reader = NotificationLogReader(notification_log)
            self.manager = record_manager
            # Position reader at max record ID.
            self.reader.seek(self.manager.get_max_record_id() or 0)

        def pull(self):
            for notification in self.reader.read():
                record = self.manager.record_class(**notification)
                self.manager._write_records([record])


    # Construct original application.
    original = SimpleApplication()

    # Construct replica application.
    replica = SimpleApplication()
    replica.persistence_policy.close()

    # Construct replicator.
    replicator = RecordReplicator(
        notification_log=original.notification_log,
        record_manager=replica.event_store.record_manager
    )

    # Publish some events.
    aggregate1 = AggregateRoot.__create__()
    aggregate1.__save__()
    aggregate2 = AggregateRoot.__create__()
    aggregate2.__save__()
    aggregate3 = AggregateRoot.__create__()
    aggregate3.__save__()

    assert aggregate1.__created_on__ != aggregate2.__created_on__
    assert aggregate2.__created_on__ != aggregate3.__created_on__

    # Check aggregates not in replica.
    assert aggregate1.id in original.repository
    assert aggregate1.id not in replica.repository
    assert aggregate2.id in original.repository
    assert aggregate2.id not in replica.repository
    assert aggregate3.id in original.repository
    assert aggregate3.id not in replica.repository

    # Pull records.
    replicator.pull()

    # Check aggregates are now in replica.
    assert aggregate1.id in replica.repository
    assert aggregate2.id in replica.repository
    assert aggregate3.id in replica.repository

    # Check the aggregate attributes are correct.
    assert aggregate1.__created_on__ == replica.repository[aggregate1.id].__created_on__
    assert aggregate2.__created_on__ == replica.repository[aggregate2.id].__created_on__
    assert aggregate3.__created_on__ == replica.repository[aggregate3.id].__created_on__

    # Create another aggregate.
    aggregate4 = AggregateRoot.__create__()
    aggregate4.__save__()

    # Check aggregate exists in the original only.
    assert aggregate4.id in original.repository
    assert aggregate4.id not in replica.repository

    # Resume pulling records.
    replicator.pull()

    # Check aggregate exists in the replica.
    assert aggregate4.id in replica.repository

    # Terminate replicator (position in notification sequence is lost).
    replicator = None

    # Create new replicator.
    replicator = RecordReplicator(
        notification_log=original.notification_log,
        record_manager=replica.event_store.record_manager
    )

    # Create another aggregate.
    aggregate5 = AggregateRoot.__create__()
    aggregate5.__save__()

    # Check aggregate exists in the original only.
    assert aggregate5.id in original.repository
    assert aggregate5.id not in replica.repository

    # Pull after replicator restart.
    replicator.pull()

    # Check aggregate exists in the replica.
    assert aggregate5.id in replica.repository

    # Setup event driven pulling. Could prompt remote
    # readers with an AMQP system, but to make a simple
    # demonstration just subscribe to local events.

    @subscribe_to(AggregateRoot.Event)
    def prompt_replicator(_):
        replicator.pull()

    # Now, create another aggregate.
    aggregate6 = AggregateRoot.__create__()
    aggregate6.__save__()
    assert aggregate6.id in original.repository

    # Check aggregate was automatically replicated.
    assert aggregate6.id in replica.repository

    # Clean up.
    original.close()

For simplicity in the example, the notification log reader uses a local
notification log in the same process as the events originated. Perhaps
it would be better to run a replication job away from the application servers,
on a node remote from the application servers, away from where the domain events
are triggered. A local notification log could be used on a worker-tier node
that can connect to the original application's database. It could equally
well use a remote notification log without compromising the accuracy of the
replication. A remote notification log, with an API service provided by the
application servers, would avoid the original application database connections
being shared by countless others. Notification log sections can be cached in
the network to avoid loading the application servers with requests from a
multitude of followers.

Since the replica application uses optimistic concurrency control for its
event records, it isn't possible to corrupt the replica by attempting
to write the same record twice. Hence jobs can pull at periodic intervals,
and at the same time message queue workers can respond to prompts pushed
to AMQP-style messaging infrastructure by the original application, without
needing to serialise their access to the replica with locks: if the two jobs
happen to collide, one will succeed and the other will encounter a concurrency
error exception that can be ignored.

Although the current implementation of the notification log reader pulls sections of
notifications in series, the sections could be pulled in parallel, which
may help when copying a very large sequence of notifications to a new replica.

The replica could itself be followed, by using its notification log. Although
replicating replicas indefinitely is perhaps pointless, it suggests how
notification logs can be potentially be chained with processing being done
at each stage.

For example, a sequence of events could be converted into a
sequence of commands, and the sequence of commands could be used to update an
event sourced index, in an index application. An event that does not affect the
projection can be recorded as "noop", so that the position is maintained. All but
the last noop could be deleted from the command log. If the command is committed
in the same transaction as the events resulting from the command, then the reliability
of the arbitrary projection will be as good as the pure replica. The events resulting
from each commands could be many or none, which shows that a sequence of
events can be projected equally reliably into a different sequence with a different
length.

Index of email addresses
~~~~~~~~~~~~~~~~~~~~~~~~

Todo: Projection into an index. Application with big array command sequence and
aggregates that represent index locations. A one-way function that goes from
real index keys to aggregate IDs. And something that runs a command before
putting it in the log, so that failures to command aggregates are tried on
the next pull. Ignore errors about creating an aggregate that already exists,
and also about discarding an aggregate that doesn't exist. Or use transactions,
if possible, so that the command and the index aggregates are updated together.
Set position of reader as max ID in command log.


Todo: Projection into a timeline view.
Todo: Projection for data analytics.
Todo: Merging notification logs ("consumer groups")?

.. Todo: Something about pumping events to a message bus, following
.. the application sequence.

.. Todo: Something about republishing events in a downstream application
.. that has subscribers such as the decorator above. Gives opportunity for
.. sequence to be reconstructed in the application before being published
.. (but then what if several views are updated and the last one fails?
.. are they all updated in the same a transaction, are do they each maintain
.. their own position in the sequence, or does the application just have one
.. subscriber and one view?)

.. Todo: So something for a view to maintain its position in the sequence,
.. perhaps version the view updates (event sourced or snapshots) if there
.. are no transactions, or use a dedicated table if there are transactions.


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
