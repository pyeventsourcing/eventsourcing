===========
Projections
===========

This section describes projecting domain events.

Projections can be updated synchronously by direct event subscription, or
asynchronously by following notification logs. Notifications can be pulled,
and pulling can be driven by subscribing to events.

.. contents:: :local:


Direct event subscription
-------------------------

The library function
:func:`~eventsourcing.domain.model.decorators.subscribe_to`
can be used to decorate functions, so that the function is called
each time a matching event is published by the library's pub-sub mechanism.

A naive projection might consume events as they are published
and update the projection without considering whether the event
was a duplicate, or if previous events were missed. This may be
perfectly adequate when beginning to develop a projection, perhaps
with tests that directly publish a sequence of events.

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
that uses messaging infrastructure. The decorator would be called
synchronously with the republishing of the event, but perhaps
asynchronously with respect to the original application.

The trouble with this approach is that, without further modification, without
referring to a fixed sequence and maintaining position in that sequence, there
is no way to recover when events have been missed. If the projection somehow
fails to update when an event is received, then the event will be lost forever to
the projection, and the projection will be forever inconsistent.

Of course it is possible to follow a fixed sequence of events, for example
using notifications.


Notification logs
-----------------

If the events of an application are presented as a sequence of
notifications, then the events can be projected using a notification
reader to pull unseen items.

Getting new items could be triggered by pushing prompts to e.g. an AMQP
messaging system, and having the remote components handle the prompts
by pulling the new notifications. To minimise load on the messaging
infrastructure, it may be sufficient simply to send an empty message,
and thereby prompt receivers into pulling new notifications. This may
reduce latency or avoid excessive polling for updates, but the benefit
would be obtained at the expense of additional complexity. Prompts
that include the position of the notification in its sequence would
allow a follower to know when it is being prompted about notifications
it already pulled, and could then skip the pulling operation.


Application state replication
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Using event record notifications, the state of an application can be
replicated perfectly. An original application presents its event
records as notifications. A "replicator" pulls notifications and writes
copies of the original records into a replica application.

With event record notifications, the ID of the record is used to sequence the
notifications. The ID of the last record in the replica is used to determine
the current position in the original sequence, which promises "exactly once"
processing, hence perfect replication.

.. code:: python

    from eventsourcing.application.simple import SimpleApplication
    from eventsourcing.exceptions import ConcurrencyError
    from eventsourcing.domain.model.aggregate import AggregateRoot
    from eventsourcing.interface.notificationlog import NotificationLogReader, RecordManagerNotificationLog


    # Define record replicator.
    class RecordReplicator(object):
        def __init__(self, reader, record_manager):
            assert isinstance(reader, NotificationLogReader)
            self.reader = reader
            self.manager = record_manager
            self.reader.seek(self.manager.get_max_record_id() or 0)

        def pull(self, *_):
            for notification in self.reader.read():
                record = self.manager.record_class(**notification)
                self.manager._write_records([record])

    # Construct original application.
    original = SimpleApplication()

    # Construct replica application.
    replica = SimpleApplication()
    replica.persistence_policy.close()

    # Construct replicator.
    reader = NotificationLogReader(original.notification_log)
    replicator = RecordReplicator(reader, replica.event_store.record_manager)

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

    # Create another aggreate.
    aggregate4 = AggregateRoot.__create__()
    aggregate4.__save__()

    # Check aggregate exists in the original only.
    assert aggregate4.id in original.repository
    assert aggregate4.id not in replica.repository

    # Resume pulling records.
    replicator.pull()

    # Check aggregate exists in the replica.
    assert aggregate4.id in replica.repository

    # Restart replicator (reader position is lost).
    reader = NotificationLogReader(original.notification_log)
    replicator = RecordReplicator(reader, replica.event_store.record_manager)

    # Create another aggreate.
    aggregate5 = AggregateRoot.__create__()
    aggregate5.__save__()

    # Check aggregate exists in the original only.
    assert aggregate5.id in original.repository
    assert aggregate5.id not in replica.repository

    # Resume pulling records after replicator restart.
    replicator.pull()

    # Check aggregate exists in the replica.
    assert aggregate5.id in replica.repository

    # Setup event driven pulling. Could prompt remote
    # readers with an AMQP system, but here subscribe
    # to local events, to make a simple demonstration.
    @subscribe_to(AggregateRoot.Created)
    def prompt_replicator(event):
        replicator.pull()

    # Create another aggregate.
    aggregate6 = AggregateRoot.__create__()
    aggregate6.__save__()
    assert aggregate6.id in original.repository

    # Check aggregate was automatically replicated.
    assert aggregate6.id in replica.repository

    # Clean up.
    original.close()


For simplicity in the example, the notification log reader uses a local
notification log, but it could equally well use a remote notification log
without compromising the accuracy of the replication. "Local" could also
mean a node which can connect to the original application's database such
as a worker-tier node, but which is remote from the application servers
where the domain events are triggered. Remote notifications would avoid
the original application database connection being shared by countless
others. Remote notification log sections can be cached in the network to
avoid loading the application servers with requests from a multitude of
followers of the notification sequence.

Although the implementation of the notification log reader gets pages of
notifications in series, the pages could be obtained in parallel, which
may help when copying a very large sequence of notifications to new replicas.


Index of email addresses
~~~~~~~~~~~~~~~~~~~~~~~~

Todo: Projection into an index.


Todo: Projection into a timeline view.
Todo: Projection for data analytics.


.. Todo: Something about pumping events to a message bus, following
the application sequence.

.. Todo: Something about republishing events in a downstream application
that has subscribers such as the decorator above. Gives opportunity for
sequence to be reconstructed in the application before being published
(but then what if several views are updated and the last one fails?
are they all updated in the same a transaction, are do they each maintain
their own position in the sequence, or does the application just have one
subscriber and one view?)

.. Todo: So something for a view to maintain its position in the sequence,
perhaps version the view updates (event sourced or snapshots) if there
are no transactions, or use a dedicated table if there are transactions.


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
