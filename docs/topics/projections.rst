===========
Projections
===========

A projection is a function of application state. If the state of an application is
event sourced, projections can operate by processing the events of an application.
There are lots of different kinds of projection.

Projected state can be updated by direct event subscription, or by following notification
logs that propagate the events of an application. Notification logs are described in the
previous section.

Notifications in a notification log can be pulled. Pulling notifications can
be prompted periodically, prompts could also be pushed onto a message bus. Notifications
could by pushed onto the message bus, but if order is lost, the projection will need to
refer to the notification log.

Projections can track the notifications that have been processed: the position
in an upstream notification log can be recorded. It is possible for the position
can be recorded as a value in the projected application state, if the nature of the
projection lends itself to be used also to track notifications. Otherwise, the position
in the notification log can be recorded with a separate tracking record.

If upstream notifications are distributed across many notification logs, then a
projection can be deployed with many concurrent operating system processes.

Any causal ordering between notifications in different logs can be maintained
if each operating system process waits until all upstream notification dependencies
have been processed, which it can do by polling for the existence of the corresponding
tracking records.

Projections can update more or less anything. To be reliable, the projection must
write in the same atomic database transaction all the records that result from
processing a notification. Otherwise it is possible to track the position
and fail to update the projection, or vice versa.

A projection that both consumes and creates notifications can be called a "process".

Since projections can update more or less anything, they can also call
command methods on event sourced aggregates. The important thing is for
any new domain events that are triggered by the aggregates to be recorded
in the same database transaction as the tracking records. For reliability,
if these new domain events are also placed in a notification log, then the
tracking record and the domain event records and the notification records
can be written in the same database transaction. A projection that operates by
calling methods on aggregates and recording events with notifications, can be
called an "application process".

Different application processes can work together as a coherent and reliable
system, for example an orders-reservations-payments system. An application
process DSL can be could describe such a system of application processes,
as function definitions that call each other, with decorators on these
functions to associate each with a policy.

Optimistic concurrency control of uniqueness constraints on the tracking and
event records would allow safe redundant processing of each application process.


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
by tracking notification logs.


Tracking notification logs
--------------------------

If the events of an application are presented as a sequence of
notifications, then the events can be projected using a notification
reader to pull unseen items.

Getting new items can be triggered by pushing prompts to e.g. an AMQP
messaging system, and having the remote components handle the prompts
by pulling the new notifications.

To minimise load on the messaging
infrastructure, it may be sufficient simply to send an empty message,
thereby prompting receivers to pull new notifications. This may
reduce latency or avoid excessive polling for updates, but the benefit
would be obtained at the cost of additional complexity. Prompts
that include the position of the notification in its sequence would
allow a follower to know when it is being prompted about notifications
it already pulled, and could then skip the pulling operation.

If an application has partitioned notification logs, they could be consumed
concurrently.

If a projection creates a sequence that it appends to at least once for each
notification, the position in the notification log can be tracked as part of
the projection's sequence. Tracking the position is important when resuming
to process the notifications. An example of using the projection's sequence
to track the notifications is replication (see example below). However, with
this technique, something must be written to the projection's sequence for
each notification received. That can be tolerated by writing "null" records
that extend the sequence without spoiling the projections, for example in
the event sourced index example below, random keys are inserted
instead of email addresses to extend the sequence.

An alternative which avoids writing unnecessarily to a projection's sequence
is to separate the concerns, and write a tracking record for each notification
that is consumed, and then optionally any records created for the projection
in response to the notification.

A tracking record can simply have the position of a notification in a log. If
the notifications are interpreted as commands, then a command log could function
effectively to track the notifications, so long as one command is written for
each notification (which might then involve "null" commands). For reliability,
the tracking records need to be written in the same atomic database
transaction as the projection records.

The library's ``Process`` class uses tracking records.

Application state replication
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Using event record notifications, the state of an application can be
replicated perfectly. If an application can present its event records
as a notification log, then a "replicator" can read the notification
log and write copies of the original records into a replica's record
manager.

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

This example is similar to the replication example above, in that notifications are
tracked with the records of the projected state. In consequence, an index entry is
added for each notification received, which means progress can be made along the
notification log even when the notification doesn't imply a real entry in the index.

.. code:: python

    import uuid

    from eventsourcing.application.simple import SimpleApplication
    from eventsourcing.exceptions import ConcurrencyError
    from eventsourcing.domain.model.aggregate import AggregateRoot
    from eventsourcing.interface.notificationlog import NotificationLogReader, RecordManagerNotificationLog

    # Define domain model.
    class User(AggregateRoot):
        def __init__(self, *arg, **kwargs):
            super(User, self).__init__(*arg, **kwargs)
            self.email_addresses = {}

        class Event(AggregateRoot.Event):
            pass

        class Created(Event, AggregateRoot.Created):
            pass

        def add_email_address(self, email_address):
            self.__trigger_event__(User.EmailAddressAdded, email_address=email_address)

        class EmailAddressAdded(Event):
            def mutate(self, aggregate):
                email_address = User.EmailAddress(self.email_address)
                aggregate.email_addresses[self.email_address] = email_address

        def verify_email_address(self, email_address):
            self.__trigger_event__(User.EmailAddressVerified, email_address=email_address)

        class EmailAddressVerified(Event):
            def mutate(self, aggregate):
                aggregate.email_addresses[self.email_address].is_verified = True

        class EmailAddress(object):
            def __init__(self, email_address):
                self.email_address = email_address
                self.is_confirmed = False

    class IndexItem(AggregateRoot):
        def __init__(self, index_value=None, *args, **kwargs):
            super(IndexItem, self).__init__(*args, **kwargs)
            self.index_value = index_value

        class Event(AggregateRoot.Event):
            pass

        class Created(Event, AggregateRoot.Created):
            pass


    def uuid_from_url(url):
        return uuid.uuid5(uuid.NAMESPACE_URL, url.encode('utf8') if bytes == str else url)


    # Define indexer.
    class Indexer(object):
        class Event(AggregateRoot.Event):
            pass
        class Created(AggregateRoot.Created):
            pass
        def __init__(self, notification_log, record_manager):
            self.reader = NotificationLogReader(notification_log)
            self.manager = record_manager
            # Position reader at max record ID.
            # - this can be generalised to get the max ID from many
            #   e.g. big arrays so that many notification logs can
            #   be followed, consuming a group of notification logs
            #   would benefit from using transactions to set records
            #   in a big array per notification log atomically with
            #   inserting the result of combining the notification log
            #   because processing more than one stream would produce
            #   a stream that has a different sequence of record IDs
            #   which couldn't be used directly to position any of the
            #   notification log readers
            # - if producing one stream from many can be as reliable as
            #   replicating a stream, then the unreliability will be
            #   caused by interoperating with systems that just do push,
            #   but the push notifications could be handled by adding
            #   to an application partition sequence, so e.g. all bank
            #   payment responses wouldn't need to go in the same sequence
            #   and therefore be replicated with mostly noops in all application
            #   partitions, or perhaps they could initially go in the same
            #   sequence, and transactions could used to project that into
            #   many different sequences, in order words splitting the stream
            #   (splitting is different from replicating many time). When splitting
            #   the stream, the splits's record ID couldn't be used to position to splitter
            #   in the consumed notification log, so there would need to be a command
            #   log that tracks the consumed sequence whose record IDs can be used to position
            #   the splitter in the notification log, with the commands
            #   defining how the splits are extended, and everything committed in a transaction
            #   so the splits are atomic with the command log
            # Todo: Bring out different projectors: splitter (one-many), combiner (many-one), repeater (one-one).
            self.reader.seek(self.manager.get_max_record_id() or 0)

        def pull(self):
            # Project events into commands for the index.
            for notification in self.reader.read():

                # Construct index items.
                # Todo: Be more careful, write record with an ID explicitly,
                # (walk the event down the stack explicity, and then set the ID)
                # so concurrent processing is safe. Providing the ID also avoids
                # the cost of computing the next record ID.
                # Alternatively, construct, execute, then record index commands in a big array.
                # Could record commands in same transaction as result of commands if commands are not idempotent.
                # Could use compaction to remove all blank items, but never remove the last record.
                if notification['event_type'].endswith('User.EmailAddressVerified'):
                    event = original.event_store.sequenced_item_mapper.from_topic_and_data(
                        notification['event_type'],
                        notification['state'],
                    )
                    index_key = uuid_from_url(event.email_address)
                    index_value = event.originator_id
                else:
                    index_key = uuid.uuid4()
                    index_value = ''

                # Todo: And if we can't create new index item, get existing and append value.
                index_item = IndexItem.__create__(originator_id=index_key, index_value=index_value)
                index_item.__save__()


    # Construct original application.
    original = SimpleApplication(persist_event_type=User.Event)

    # Construct index application.
    index = SimpleApplication(persist_event_type=IndexItem.Event)

    # Setup event driven indexing.
    indexer = Indexer(
        notification_log=original.notification_log,
        record_manager=index.event_store.record_manager
    )

    @subscribe_to(User.Event)
    def prompt_indexer(_):
        indexer.pull()

    user1 = User.__create__()
    user1.__save__()
    assert user1.id in original.repository
    assert user1.id not in index.repository

    user1.add_email_address('me@example.com')
    user1.__save__()

    index_key = uuid_from_url('me@example.com')
    assert index_key not in index.repository

    user1.verify_email_address('me@example.com')
    user1.__save__()
    assert index_key in index.repository
    assert index.repository[index_key].index_value == user1.id

    assert uuid_from_url(u'mycat@example.com') not in index.repository

    user1.add_email_address(u'mycat@example.com')
    user1.verify_email_address(u'mycat@example.com')
    user1.__save__()

    assert uuid_from_url(u'mycat@example.com') in index.repository

    assert user1.id in original.repository
    assert user1.id not in index.repository



----

Todo: Projection into a timeline view?

Todo: Projection into snapshots (policy determines when to snapshot)?

Todo: Projection for data analytics?

Todo: Concurrent processing of notification logs, respecting causal relations.

Todo: Order reservation payments, system with many processes and many notification logs.

Todo: Single process with single log.

Todo: Single process with many logs.

Todo: Many processes with one log each.

Todo: Many processes with many logs each (static config).

Todo: Many processes with many logs each (dynamic config).

Todo: Single process with state machine semantics (whatever they are)?


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
