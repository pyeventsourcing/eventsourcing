===========
Projections
===========

This section shows how events can be projected into things other than aggregates.

The library's ``@subscribe_to`` decorator is described, which causes the
decorated function to be called each time an event of a given type is
published by the library's pub-sub mechanism. It can be used to update
projections as events are published by an application.

An asynchronous approach which uses the library's notifications is introduced.


.. contents:: :local:


Published events
----------------

The library decorator function
:func:`~eventsourcing.domain.model.decorators.subscribe_to`
can be used to subscribe to events as they are published by
the library's pub-sub mechanism.

A very simple implementation of a projection would consume
an event synchronously as it is published by updating the
view without considering whether the event was a duplicate
or previous events were missed. This may be perfectly adequate
for projections that are by design independent, such as
tracking all 'Created' events so the extent aggregate IDs are
available in a view.

Of course, it is possible to access aggregates and other views when
updating a view, especially to avoid bloating events with redundant
information that might be added to avoid such queries.

The example below suggests that record ``TodoView`` can be created
whenever a ``Todo.Created`` event is published. Perhaps the ``TodoView``
table has an index of todo titles, or can be joined with a table of users.

.. code::

    @subscribe_to(Todo.Created)
    def new_todo_projection(event):
        todo = TodoView(id=event.originator_id, title=event.title, user_id=event.user_id)
        todo.save()


The trouble with this approach is that position in the application is being maintained.
So if the view somehow fails to update after the domain event has been stored,
then the event will be lost to the projection, which will not eventually become consistent.

It is possible to use the decorator in a downstream application, in
which domain events are republished following the application
sequence asynchronously. The decorator would be called synchronously with the
republishing of the event. In this case, if the view update routine somehow
fails to update, the position of the downstream application in the upstream
sequence would not advance until the view is restored to working order, after
which the view will be updated as if there had been no failure.

It is also possible for a synchronous update to refer to an application
log and catch up if necessary, perhaps after an error or because
the projection is new to the application and needs to initialise.


Notifications
-------------

If the events of an application are presented as a sequence of
notifications, then a notification reader can be used to get new
notifications, and the notifications can be projected.

Getting notifications can triggered by pushing prompts to e.g. an AMQP
messaging system, and having the remote components handle the prompts
by pulling new notifications.

To minimise load on the messaging infrastructure, it may be sufficient
simply to send an empty message, and thereby prompt receivers into pulling
new notifications.


Examples
--------

Using notifications, the state of an application can be perfectly replicated,
by replicating its stored event records with event record notifications. In
the example below, a notification log reader uses a local notification log,
but it could equally well use a remote notification log.

With record notifications, the ID of the record is used to sequence the
notifications. Hence the ID of the last record in the replica can be used
to determine the current position in the original sequence.

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

    # Setup event driven pulling.
    from eventsourcing.domain.model.events import subscribe, unsubscribe

    # Subscribe to local events, could use AMQP system so original can prompt remote replicas.
    subscribe(handler=replicator.pull, predicate=original.persistence_policy.is_event)

    # Create another aggregate.
    aggregate6 = AggregateRoot.__create__()
    aggregate6.__save__()
    assert aggregate6.id in original.repository

    # Check aggregate was automatically replicated.
    assert aggregate6.id in replica.repository

    # Clean up.
    unsubscribe(handler=replicator.pull)
    original.close()


Todo: Projection example: projection into an index.
Todo: Projection example: projection into a timeline view.
Todo: Projection example: projection for data analytics.


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
