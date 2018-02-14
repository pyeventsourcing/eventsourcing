===========
Projections
===========

Updating projections
--------------------

Once the events of an application can be followed reliably, for example
as notifications, they can be used to update projections of the application state.

Todo: Separate this into a doc about projections, start with a log reader...
Todo: Projection example: perfect replication of the application state.
Todo: Projection example: projection into an index.
Todo: Projection example: projection into a timeline view.
Todo: Projection example: projection for data analytics.


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
