==================
Process and system
==================

The most important requirement pursued in this section is to obtain a reliable
process. A process is considered to be reliable if the product is unaffected
by sudden terminations of the process, except in being delayed until the
processing is resumed.

Process is understood as productive in the following sense: consumption with recording
determines production. If the consumption and the recording are reliable, then for so
long as processing can happen at all, production will also be reliable. By extension,
a system composed exclusively of reliable processes will also be reliable.

The definition of "reliability" doesn't include "availability". A disorderly environment
shouldn't cause disorderly processing. Infrastructure failures should only cause processing
*delays*.

To limit the scope of this discussion, it is assumed here that whatever records
have been committed by a process are not somehow damaged by random sudden
terminations of the process. But a record is not a process, and the reliability
of records is beyond the scope of this discussion.

(Please note, the code in these examples currently only works with SQLAlchemy record
manager. Django support is planned. Cassandra support is being considered.)

.. contents:: :local:


Process application
-------------------

The library's process class, ``Process``, functions as both an event-sourced projection
(see previous section) and as an event-sourced application. It is a subclass of
``SimpleApplication`` that also has a notification log reader and tracking records. It
also has a policy that defines how the process responds to events.

A process application consumes events by reading event notifications from its notification
log reader. The events are retrieved in a reliable order, without race conditions or
duplicates or missing items.

To keep track of its position in the notification log, a process application will create
a new tracking record for each notification. The tracking records determine how far the
process has progressed through the notification log. They are used to set the position
of the notification log reader when the process is commenced or resumed.

A process application will respond to events according to its policy. Its policy might
do nothing in response to one type of event, and it might call an aggregate method in
response to another type of event.

However the policy responds to an event, the process application will write a tracking
record, along with any new event records, in an atomic database transaction.

Most importantly, if some of the new records can't be written, then none are. If anything
goes wrong before all the records have been written, the transaction will rollback, none
of the records will be written, and the process will not have progressed. On the other hand,
if the tracking record has been written, then so will any new event records, and the process
will have fully completed an atomic progression.

Furthermore, there can only be one unique tracking record for each notification.
Once the tracking record has been written it can't be written again, and neither can
any new events unfortunately triggered by duplicate calls to aggregate commands (which
may even succeed and which may not be idempotent). If an event can be processed at all,
then it will be processed exactly once.

The processing will be reliable even if the behaviour of the policies and the aggregates
is dysfunctional. Like the ratchet is as reliable as its pawl, a process application
is as reliable as its database transactions are atomic.


System of processes
-------------------

One such process could follow another in a system of processes. One process could follow two
other processes in a slightly more complicated system. A process could simply follow
itself, stepping though state transitions that involve many aggregates. There could
be a vastly complicated system of processes without introducing any systemically
emergent unreliability in the processing of the events (it is "absolutely" reliable,
there isn't somehow a "tolerable" level of unreliability in each process that would eventually
compound into an intolerable level of unreliability in a complicated system of processes).

A number of application processes could be run from a single thread. Alternatively, they
could each have one thread in a single process. Each thread could have its own operating
system process, and each operating system process could run on its own machine. Although
there is parallelism in such a system, this isn't the kind of parallelism that will
allow the system to scale horizontally (adding more machines).

To scale the throughput of a process horizontally, beyond the rate at which
a single sequence can be processed in series, notifications could be divided
across many notification logs. Each notification log could be processed
concurrently. Hence one application process could usefully and reliably employ many concurrent
operating system processes. This feature is demonstrated below.

In the example below, a system of process applications is defined independently of
how it may be run. The process application use a domain model with three aggregates.
The process applications each have a policy, which defines how they respond to events
received by the application in notification logs of the applications it is following.
The system is run as a single threaded system. Afterwards, the system is run with with
partitioned notification logs and multiprocessing, so there is one operating system
process for each partition for each process application in the system, all of which
then operate concurrently, demonstrating both kinds of parallelism.


Kahn process networks
~~~~~~~~~~~~~~~~~~~~~

Since a notification log functions effectively as a durable FIFO buffer, a system of
determinate process applications pulling notifications logs can be recognised as a
`Kahn Process Network <https://en.wikipedia.org/wiki/Kahn_process_networks>`__ (KPN).

Kahn Process Networks are determinate systems. If a system of process applications
happens to involve processes that are not determinate, the system as a whole will
not be determinate, and could be described in more general terms as "dataflow" or
"stream processing". However, in these cases, it may help that some components
are determinate.


Orders, reservations, payments
------------------------------

The example below is suggestive of an orders-reservations-payments system.
The system automatically processes new orders by making a reservation and
then a payment, facts registered with the order.

Aggregates
~~~~~~~~~~

In the code below, event-sourced aggregates are defined for orders, reservations,
and payments. The ``Order`` class is for "orders". The ``Reservation`` class is
for "reservations". And the ``Payment`` class is for "payments".

A new ``Order`` aggregate can be created. An unreserved order
can be set as reserved, which involves a reservation
ID. Having been created and reserved, an order can be
set as paid, which involves a payment ID.

.. code:: python

    from eventsourcing.domain.model.aggregate import AggregateRoot


    class Order(AggregateRoot):
        def __init__(self, **kwargs):
            super(Order, self).__init__(**kwargs)
            self.is_reserved = False
            self.is_paid = False

        class Event(AggregateRoot.Event):
            pass

        class Created(Event, AggregateRoot.Created):
            pass

        def set_is_reserved(self, reservation_id):
            self.__trigger_event__(Order.Reserved, reservation_id=reservation_id)

        class Reserved(Event):
            def mutate(self, order):
                assert not order.is_reserved, "Order {} already reserved.".format(order.id)
                order.is_reserved = True
                order.reservation_id = self.reservation_id

        def set_is_paid(self, payment_id):
            self.__trigger_event__(self.Paid, payment_id=payment_id)

        class Paid(Event):
            def mutate(self, order):
                assert not order.is_paid, "Order {} already paid.".format(order.id)
                order.is_paid = True
                order.payment_id = self.payment_id


A ``Reservation`` can be created.

.. code:: python

    class Reservation(AggregateRoot):
        def __init__(self, order_id, **kwargs):
            super(Reservation, self).__init__(**kwargs)
            self.order_id = order_id

        class Event(AggregateRoot.Event):
            pass

        @classmethod
        def create(cls, order_id):
            return cls.__create__(order_id=order_id)

        class Created(Event, AggregateRoot.Created):
            pass


And a ``Payment`` can be made.

.. code:: python

    class Payment(AggregateRoot):
        def __init__(self, order_id, **kwargs):
            super(Payment, self).__init__(**kwargs)
            self.order_id = order_id

        class Event(AggregateRoot.Event):
            pass

        @classmethod
        def make(self, order_id):
            return self.__create__(order_id=order_id)

        class Created(Event, AggregateRoot.Created):
            pass


The orders factory ``create_new_order()`` is decorated with the ``@retry`` decorator,
to be resilient against both concurrency conflicts and operational errors.

.. Todo: Raise and catch ConcurrencyError instead of RecordConflictError.

.. code:: python

    from eventsourcing.domain.model.decorators import retry
    from eventsourcing.exceptions import OperationalError, RecordConflictError

    @retry((OperationalError, RecordConflictError), max_attempts=10, wait=0.01)
    def create_new_order():
        """Orders factory"""
        order = Order.__create__()
        order.__save__()
        return order.id

As shown in previous sections, the behaviours of this domain model can be fully tested
with simple test cases, without involving any other components.


Processes
~~~~~~~~~

The processes of the orders-reservations-payments system have
policies that respond to domain events by executing commands.

In the code below, the Orders process responds to new reservations
by setting the order as reserved. The Reservations process responds
to new orders by creating a reservation. The Orders process responds
to new payments by setting the order as paid. And the Payments
process responds to orders being reserved by making a payment.

The library's ``Process`` class is a subclass of the library's
``SimpleApplication`` class.

.. code:: python

    from eventsourcing.application.process import Process


    class Orders(Process):
        persist_event_type=Order.Created

        def policy(self, repository, event):
            if isinstance(event, Reservation.Created):
                # Set order is reserved.
                order = repository[event.order_id]
                assert not order.is_reserved
                order.set_is_reserved(event.originator_id)

            elif isinstance(event, Payment.Created):
                order = repository[event.order_id]
                assert not order.is_paid
                order.set_is_paid(event.originator_id)


    class Reservations(Process):
        def policy(self, repository, event):
            if isinstance(event, Order.Created):
                # Create a reservation.
                return Reservation.create(order_id=event.originator_id)


    class Payments(Process):
        def policy(self, repository, event):
            if isinstance(event, Order.Reserved):
                # Make a payment.
                return Payment.make(order_id=event.originator_id)

Please remember, do not call the ``__save__()`` method of aggregates, the
pending events will be collected after the ``policy()`` method has been called.

The policies are easy to test. Here's a test for the payments policy.

.. code:: python

    def test_payments_policy():

        # Prepare fake repository with a real Order aggregate.
        order = Order.__create__()
        fake_repository = {order.id: order}

        # Check policy makes payment whenever order is reserved.
        event = Order.Reserved(originator_id=order.id, originator_version=1)

        with Payments() as process:
            payment = process.policy(repository=fake_repository, event=event)
            assert isinstance(payment, Payment), payment
            assert payment.order_id == order.id

    # Run the test.
    test_payments_policy()


In this test, a new aggregate is created by the policy, and checked by the test.
The test is able to check the new aggregate because the new aggregate is returned
by the policy. Policies should normally return new aggregates to the caller.
Remember, do not call the __save__() method of new aggregates: their pending
events will be collected after the ``policy()`` method has returned.

If a policy retrieves and changes an already existing aggregate, the aggregate does
not need to be returned by the policy to the caller. Again, there is no need to call
the ``__save__()`` method of changed aggregates, pending events will be collected
 after the ``policy()`` method has finished. The test will already have a reference
to the aggregate, because it will have constructed the aggregate before passing it
to the policy, so the test will be in a good position to check the aggregate changes
as expected.

Here's a test for the orders policy responding to a ``Reservation.Created``
event. It shows how a policies that change already existing aggregates can
be tested.

.. code:: python

    from uuid import uuid4

    def test_orders_policy():
        # Prepare fake repository with a real Order aggregate.
        order = Order.__create__()
        fake_repository = {order.id: order}

        # Check order is not reserved.
        assert not order.is_reserved

        # Check order is set as reserved when reservation is created for the order.
        with Orders() as process:

            event = Reservation.Created(originator_id=uuid4(), originator_topic='', order_id=order.id)
            process.policy(repository=fake_repository, event=event)

        # Check order is reserved.
        assert order.is_reserved

    # Run the test.
    test_orders_policy()


In normal use, the ``policy()`` method is called by the ``call_policy()``
method of the ``Process`` class, when new events are retrieved from an upstream
notification log. The ``call_policy()`` method wraps the process application's
aggregate repository with a wrapper that detects which aggregates are used by
the policy and which were changed, so any changes caused by the policy can be
automatically detected, and new records automatically committed. Returning a
new aggregate is necessary to include its events in this atomic recording.

New events are collected by requesting pending events from the aggregates.
The policy shouldn't call aggregate ``__save__()`` methods for this reason.

Causal dependencies between events could be detected and used to synchronise
the processing of different partitions downstream, so that downstream
processing of one partition can wait for an event to be processed in another.

The causal dependencies could be automatically inferred by detecting the originator
ID and version of aggregates as they are retrieved from the wrapped repository. Those
events could be examined to see if they were notified in a different partitions. If so,
the event originator ID and version of the last event in each partition could be included
in the notification. Then followers could wait for the corresponding tracking records to
appear, and then continue by processing the causally dependent notification.

(Causal dependencies not implemented, yet.)


System
~~~~~~

The system can now be defined as a network of processes that follow each other.

The library's ``System`` class can be constructed with sequences of
process classes, that show which process follows which other process
in the system. For example, sequence (A, B, C) shows that B follows A,
and C follows B. The sequence (A, A) shows that A follows A.
The sequence (A, B, A) shows that B follows A, and A follows B.
The sequences ((A, B, A), (A, C, A)) is equivalent to (A, B, A, C, A).

In this example, the orders and the reservations processes follow
each other. Also the payments and the orders processes follow each
other. There is no direct relationship between reservations and payments.

.. code:: python

    from eventsourcing.application.process import System


    system = System(
        (Orders, Reservations, Orders, Payments, Orders),
    )


In this system, the Orders process, specifically the Order aggregate
combined with the Orders process policy, is more or less equivalent to
"saga", or "process manager", or "workflow", in that it effectively
controls a sequence of steps involving other bounded contexts and
aggregates, steps that would otherwise perhaps be controlled with a
"long-lived transaction". The convoluted design, of running everything
through orders aggregate, is supposed to demonstrate how an aggregate
can control a sequence of transactions. A simpler design, the payments
process would respond directly to the reservation events.

In this design, except for the definition and implementation of process,
there are no special concepts or components. There are only policies and
aggregates and events, and the way they are processed in a process application.
There isn't a special mechanism that provides reliability despite the rest
of the system, each aggregate is equally capable of functioning as a saga object,
every policy is capable of functioning as a process manager or workflow.
There doesn't need to be a special mechanism for coding compensating
transactions. If required, a failure (e.g. to make a payment) can be
coded as an event that can processed to reverse previous steps (e.g.
to cancel a reservation).


Single threaded system
----------------------

If the ``system`` object is used as a context manager, the process
applications will be setup to work in the current process. Events
will be processed with a single thread of execution, with synchronous
handling of prompts, so that policies effectively call each other
recursively. This avoids concurrency and is useful when developing
and testing a system of process applications.

In the code below, the ``system`` object is used as a context manager.
In that context, a new order is created. The system responds
by making a reservation and a payment, facts that are registered
with the order. Everything happens synchronously, in a single
thread, so by the time the ``create_new_order()`` factory
has returned, the system has already processed the order,
which can be retrieved from the "orders" repository.

.. code:: python

    with system:
        # Create new Order aggregate.
        order_id = create_new_order()

        # Check the order is reserved and paid.
        repository = system.orders.repository
        assert repository[order_id].is_reserved
        assert repository[order_id].is_paid


The process applications above could be run in different threads (not
yet implemented).

Multiprocessing system
----------------------

The example below shows the system of process applications running in
different processes on the same node, using the library's ``Multiprocess``
class, which uses Python's ``multiprocessing`` library.

With multiple threads or operating system processes, each process can run
a loop that begins by making a call to messaging infrastructure for prompts
pushed from upstream via messaging infrastructure. Prompts can be responded
to immediately by pulling new notifications. If the call to get new prompts
times out, any new notifications from upstream notification logs can be pulled
anyway, so that the notification log is effectively polled at a regular
interval. The ``Multiprocess`` class happens to use Redis publish-subscribe
to push prompts.

The process applications could all use the same single database, or they
could each use their own database.
If the process applications use different databases, upstream notification
logs could to be presented in an API, and downstream could pull notifications
from an upstream API using a remote notification log object (as discussed in
a previous section).

In this example, the process applications use the same MySQL database. However,
even though all the process applications use the same database, the aggregates
are segregated in their process application, so each application can only access
its own aggregates from its repository. The state of a process application is
only available to others applications by propagating events in notification
logs. The example works just as well with PostgreSQL.

.. code:: python

    import os

    os.environ['DB_URI'] = 'mysql+mysqlconnector://root:@127.0.0.1/eventsourcing'
    #os.environ['DB_URI'] = 'postgresql://username:password@localhost:5432/eventsourcing'


The multiprocessing system notification logs will be partitioned. Partitioning
will cause three separate instances of the system running concurrently, sharing
the same database. Aggregates of an application are available to all partitions
of that application. Partitioning can be configured statically. (Dynamic
configuration is not yet implemented, Auto-scaling is being considered).

This example uses three partitions, each identified in the records with a UUID.

.. code:: python

    from uuid import uuid4

    # These should be static configuration values.
    partition_ids = [uuid4(), uuid4(), uuid4()]


Before starting the system's operating system processes, let's create a new order aggregate.
The Orders process is constructed so that any ``Order.Created`` events published by the
``create_new_order()`` factory will be persisted. The process application needs to be
told which partition to use for the event notification.

.. code:: python

    from eventsourcing.application.simple import SimpleApplication

    with Orders(setup_tables=True, partition_id=partition_ids[0]) as app:

        # Create a new order.
        order_id = create_new_order()

        # Check new order exists in the repository.
        assert order_id in app.repository


The MySQL database tables were created by the code above, because the ``Orders`` process
was constructed with ``setup_tables=True``, which is by default ``False`` in the ``Process``
class.

The library's ``Multiprocess`` class can be used to run the ``system``. The system
is run with three partitions. There is one operating system process for each partition
for each application process, which makes nine operating system processes.
This system example can work with partitions because there are no causal dependencies
between events in different partitions. (Causal dependencies not yet implemented.)

The ``multiprocess`` object is constructed with the list of ``partition_ids``.

.. code:: python

    from eventsourcing.application.multiprocess import Multiprocess

    multiprocess = Multiprocess(system, partition_ids=partition_ids)


The operating system processes can be started by using ``multiprocess`` as a
context manager (calls ``start()`` on entry and ``close()`` on exit). Wait
for the results, by polling the aggregate state.

.. code:: python

    import time

    if __name__ == '__main__':

        # Start multiprocessing system.
        with multiprocess, Orders() as app:

                retries = 50
                while not app.repository[order_id].is_reserved:
                    time.sleep(0.1)
                    retries -= 1
                    assert retries, "Failed set order.is_reserved"

                while retries and not app.repository[order_id].is_paid:
                    time.sleep(0.1)
                    retries -= 1
                    assert retries, "Failed set order.is_paid"


Let's do that again, but with a batch of orders that is created after the system
operating system processes have been started. Below, ``app`` will be working
concurrently with the ``multiprocess`` system, which causes contention.
Twenty-five orders are created in each partition, making seventy-five
event-sourced orders in total, processed reliably, with two different kinds
of parallelism, and contention.

.. code:: python

    import datetime

    if __name__ == '__main__':

        # Start multiprocessing system.
        with multiprocess:

            # Create some new orders.
            #num = 250
            num = 25
            order_ids = []

            for _ in range(num):

                for partition_id in partition_ids:

                    with Orders(partition_id=partition_id) as app:

                        order_id = create_new_order()
                        order_ids.append(order_id)

                        multiprocess.prompt_about('orders', partition_id)


            # Wait for orders to be reserved and paid.
            with Orders() as app:
                retries = 10 * num * len(partition_ids)
                for i, order_id in enumerate(order_ids):

                    while not app.repository[order_id].is_reserved:
                        time.sleep(0.1)
                        retries -= 1
                        assert retries, "Failed set order.is_reserved {} ({})".format(order_id, i)

                    while retries and not app.repository[order_id].is_paid:
                        time.sleep(0.1)
                        retries -= 1
                        assert retries, "Failed set order.is_paid ({})".format(i)

                # Print timings.
                orders = [app.repository[oid] for oid in order_ids]
                first_timestamp = min([o.__created_on__ for o in orders])
                last_timestamp = max([o.__last_modified__ for o in orders])
                duration = last_timestamp - first_timestamp
                rate = len(order_ids) / float(duration)
                period = 1 / rate
                print("Orders system processed {} orders in {:.3f}s at rate of {:.1f} "
                      "orders/s, {:.3f}s each".format(len(order_ids), duration, rate, period))

                # Print min, average, max duration.
                durations = [o.__last_modified__ - o.__created_on__ for o in orders]
                print("Min order processing time: {:.3f}s".format(min(durations)))
                print("Mean order processing time: {:.3f}s".format(sum(durations) / len(durations)))
                print("Max order processing time: {:.3f}s".format(max(durations)))


Running the system with multiple operating system processes means the different steps
for processing an order happen concurrently, so that as a payment is being made for one
order, the next order might concurrently be being reserved, whilst a third order is at
the same time being created. Because of the partitioning, a fourth, fifth and sixth
order may be being processed in the next partition. And so on for all the partitions.

Because the orders are created with a second instance of the ``Orders`` process
application, rather than e.g. a command process application that is followed
by the orders process, there will be contention and conflicts writing to the
orders process notification log. The example was designed to cause this contention,
and the ``@retry`` decorator was applied to the ``create_new_order()`` factory, so
when conflicts are encountered, the operation will be retried and will most probably
eventually succeed. For the same reason, the same ``@retry``  decorator is applied
the ``run()`` method of the library class ``Process``.

In case retries are exhausted,
the original exception will be reraised by the decorator. But when the process
application is run with ``Multiprocess``, it runs a loop which will catch exceptions,
and the process will be reset from committed records, and processing will start
again, looping indefinitely until the process is closed (or terminated).


Actor model system
------------------

An Actor model library, such as `Thespian Actor Library
<https://github.com/kquick/Thespian>`__, could be used to run
a system of process applications as actors.

Actors could be run on different nodes in a cluster. Actors could
be supervised, so that failures could be reported, and actors restarted.

Prompts could be sent as actor messages, rather than with a publish-subscribe service.

To aid development and testing, actors could run without any
parallelism, for example with the "simpleSystemBase" actor
system in Thespian.

However, it seems that actors aren't a very reliable way of propagating application
state. The reason is that actor frameworks will not, in a single atomic transaction,
remove an event from its inbox, and also store new domain events, and also write
to another actor's inbox. Hence, for any given message that has been received, one
or two of those things could happen whilst the other or others do not.

For example what happens when the actor suddenly terminates after a new domain event
has been stored but before the event can be sent as a message? Will the message never be sent?
If the actor records which messages have been sent, what if the actor suddenly terminates after
the message is sent but before the sending could be recorded? Will there be a duplicate?

Similarly, if normally a message is removed from an actor's inbox and then new domain
event records are made, what happens if the actor suddenly terminates before the new
domain event records can be committed?

If something goes wrong after one thing has happened but before another thing
has happened, resuming after a breakdown will cause duplicates or missing items
or a jumbled sequence. It is hard to understand how this situation can be made reliable.

And if a new actor is introduced after the application has been generating events
for a while, how does it catch up? If there is a separate way for it to catch up,
switching over to receive new events without receiving duplicates or missing events
or stopping the system seems like a hard problem.

In some applications, reliability may not be required, for example with some
analytics applications. But if reliability does matter, if accuracy if required,
remedies such as resending and deduplication, and waiting and reordering, seem
expensive and complicated and slow. Idempotent operations are possible but it
is a restrictive approach. Even with no infrastructure breakdowns, sending messages
can overrun unbounded buffers, and if the buffers are bounded, then write will block.
The overloading can be remedied by implementing back-pressure, for which a standard
has been written.

Even if durable FIFO channels were used to send messages between actors, which would
be quite slow relative to normal actor message sending, unless the FIFO channels were
written in the same atomic transaction as the stored event records, and removing the
received event from the in-box, in other words, the actor framework and the event
sourcing framework were intimately related, the process wouldn't be reliable.

Altogether, this collection of issues and remedies seems exciting at first but mostly
inhibits confidence that the actor model offers a simple, reliable, and maintainable
approach to propagating the state of an application. It seems like a unreliable
approach for projecting the state of an event sourced application, and therefore cannot
be the basis of a reliable system that processes domain events by generating other
domain events. Most of the remedies each seem much more complicated than the notification
log approach implemented in this library.

It may speed a system to send events as messages, and if events are sent as messages
and they happen to be received in the correct order, they can be consumed in that way,
which should save reading new events from the database, and will therefore help to
avoid the database bottlenecking event propagation, and also races if the downstream
process is reading notifications from a lagging database replica. But if new events are generated
and stored because older events are being processed, then to be reliable, to underwrite the
unreliability of sending messages, the process must firstly produce reliable
records, before optionally sending the events as prompts. It is worth noting that sending
events as prompts loads the messaging system more heavily that just sending empty prompts,
so unless the database is a bottleneck for reading events, then sending events as
messages might slow down the system (sending events is slower than sending empty prompts
when using multiprocessing and Redis on a laptop).

The low-latency of sending messages can be obtained by pushing empty prompts. Prompts could
be rate limited, to avoid overloading downstream processes, which wouldn't involve any loss
in the delivery of events to downstream processes. The high-throughput of sending events as
messages directly between actors could help avoid database bandwidth problems. But in case
of any disruption to the sequence, high-accuracy in propagating a sequence of events can be
obtained, in the final resort if not the first, by pulling events from a notification log.

Although sending events as messages with actors doesn't seem to offer a very reliable
way of processing domain events for applications with event-sourced aggregates, actors
do seem like a great way of orchestrating event-sourced process applications. The "based
on physics" thing seems to fit well with infrastructure, which is inherently imperfect.
If an actor fails then it can be resumed. We just need to make sure that the recorded
state of our application determines the subsequent processing, and the recorded state
is changed atomically from one coherent state to another, so that processing can resume
in a coherent state as if there was no failure, and so that infrastructure failures only
cause processing delays.

(Running a system of process applications with actors is not yet implemented in the library.)


Todo: Actor model deployment of system.


Integration with APIs
---------------------

Integration with systems that present a server API or otherwise need to
be sent messages (rather than using notification logs), can be integrated by
responding to events with a policy that uses a client to call the API or
send a message. However, if there is a breakdown during the API call, or
before the tracking record is written, then to avoid failing to make the call,
it may happen that the call is made twice. If the call is not idempotent,
and is not otherwise guarded against duplicate calls, there may be consequences
to making the call twice, and so the situation cannot really be described as reliable.

If the server response is asynchronous, any callbacks that the server will make
could be handled by calling commands on aggregates. However, if callbacks might
be retried, perhaps because the handler crashes after successfully calling a
command, unless the callbacks are also tracked (with exclusive tracking records
written atomically with new event and notification records) the aggregate commands
will need to be idempotent, or otherwise guarded against duplicate callbacks. Such
an integration could be implemented as a separate "push-API adapter" process, and
it might be useful to have a generic implementation that can be reused, with
documentation describing how to make such an integration reliable, however the
library doesn't currently have any such adapter process classes or documentation.



.. Todo: Have a simpler example that just uses one process,
.. instantiated without subclasses. Then defined these processes
.. as subclasses, so they can be used in this example, and then
.. reused in the operating system processes.

.. Todo: "Instrument" the tracking records (with a notification log?) so we can
.. measure how far behind downstream is processing events from upstream.

.. Todo: Maybe a "splitting" process that has two applications, two
.. different notification logs that can be consumed separately.

.. Todo: It would be possible for the tracking records of one process to
.. be presented as notification logs, so an upstream process
.. pull information from a downstream process about its progress.
.. This would allow upstream to delete notifications that have
.. been processed downstream, and also perhaps the event records.
.. All tracking records except the last one can be removed. If
.. processing with multiple threads, a slightly longer history of
.. tracking records may help to block slow and stale threads from
.. committing successfully. This hasn't been implemented in the library.
