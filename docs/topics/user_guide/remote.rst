=============================
Projections and notifications
=============================

Synchronous update
------------------

In a simple situation, you may wish just to synchronously
update a view of an entity when it changes. If the a view
model depends only on one aggregate - just subscribe to the
aggregate's base event class, and whenever an event occurs
get the aggregate events, construct the state of the view
from the events, and then update the view. The view could
be stored in a sequence that follows the originator version
numbers, so that concurrent handling of events will not lead
to a later state being overwritten by an earlier state. Older
version of the view can be deleted as a safe background task,
to avoid swamping a partition.

Todo: example, perhaps using the subscribe decorator


If the view fails to update after the event has been stored,
then the view will be inconsistent with the latest state
of the aggregate. Since it is not desirable to delete the
event once it has been stored, the command must return
successfully despite the view update failing, so that the command
is not retried. Without further refinements, the view will
only be updated next time the entity changes.

Also, if the first event of an aggregate is not applied to a
view, there is no way for the view context to know that aggregate
exists and so cannot possibly check for updates e.g. with
a "round robin" approach to monitoring for missing updates.

This last concern brings us to wanting a single application log
that sequences all the events in a bounded context.

Application log
---------------

In order to update a view of the bounded context as a whole,
of more than one aggregate, we need a single sequence for all of
the events in the bounded context.

Writing an application log brings its own difficulties, in particular
how to generate a single sequence in a multi-threaded application,
and how to store a large sequence of events without either swamping
one partition in a database or distributing things across
partitions so much that iterating through the sequence is slow and
expensive. The library class BigArray attempts to provide a solution
to these concerns.

The application log can be used in a persistence policy, and
can be updated before the domain event is written to the aggregate's
own sequence, so that it isn't possible to have an event in the aggregate
sequence that is not already in the application sequence. Events in the
application sequence that aren't in the aggregate sequence should be
ignored, so that the aggregate sequences remain normative. Commands
that fail to write to the aggregate's sequence after the event has been
logged in the application's sequence should raise an exception, so
that the command may be retried.


Asynchronous update
-------------------

Asynchronous updates are required for updating other aggregates,
especially updating aggregates in another bounded context.

The fundamental concern is to accomplish high fidelity when
propagating a stream of events, so that events are neither
missed nor are they duplicated. As Vaugn Vernon suggests
in his book Implementing Domain Driven Design:

    “at least two mechanisms in a messaging solution must always be consistent with each other: the persistence store used by the domain model, and the persistence store backing the messaging infrastructure used to forward the Events published by the model. This is required to ensure that when the model’s changes are persisted, Event delivery is also guaranteed, and that if an Event is delivered through messaging, it indicates a true situation reflected by the model that published it. If either of these is out of lockstep with the other, it will lead to incorrect states in one or more interdependent models.”

He gives three options.
The first option is to have the messaging infrastructure and
the domain model share the same persistence store, so changes
to the model and insertion of new messages
happen commit in the same local transaction.

The second option
is to have separate datastores for domain model and messaging
but have a two phase commit, or global transaction, across
the two.

The third option is to have the bounded context
control sending messages to the messaging infrastructure,
so that it knows what remains to be sent, almost like a local
projection. A pull mechanism that allows others to pull events
that they don't yet have can be used either instead of push
notifications, or as a way to allows remote clients to catch
up when they detect events have been missed.

It is the third approach that Vaughn uses in his examples,
and it is the third approach that is taken here.

The approach taken by Vaughn
Vernon is his book Implementing Domain Driven Design is to
rely on the simple logic of an ascending sequence of integers
to detect when an event has been missed, and when it has been
duplicated. Notification logs, with their current log and
archived logs are used to pull a sequence reliably. Publish-
subscribe can be used to push events, but clients may need
to fall back onto pulling events that have not been received.

This implies two things: a log in the originating context that spans
all the aggregates in an application; and in the receiving
context, something to track the position of the last event that
was applied.

The BigArray class, used with a number generator, can be used
to log references to all the events in a bounded context. Any
projections from the application sequence can be versioned according
to same sequence, so that updates can be made in a stable manner.

The same interface to the big array can be used locally and remotely,
with the remote array object depending on a strategy for pulling
events perhaps from a RESTful API.

Since subscribers to push notifications may detect they are missing
an event, and will need to pull missing events. In any case, they may
arrive late to the application and require initialising from an
established application stream, or otherwise need to be reconstructed
from scratch. So attention is given next to notification logs, which
may present the application log.

Notification log
----------------

The RESTful API design in Implementing Domain Driven Design
suggests a good way to present the application log, a way that
is simple and can scale using established HTTP technology.
