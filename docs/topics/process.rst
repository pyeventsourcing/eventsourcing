==================
Process and system
==================

Process is understood as productive in the following sense: consumption with recording
determines production. For example, if consumption and recording are reliable, then
production will be reliable. A system composed exclusively of reliable processes
will also be reliable.

The most important requirement pursued in this section is to obtain a reliable
process. A process is reliable if its product is entirely unaffected by sudden
termination of the process happening at any time, except in being delayed
until the processing is resumed.

This definition of the reliability of a process doesn't include availability.
Obviously without any infrastructure, the processing will be delayed indefinitely.
Infrastructure unreliability may cause processing delays but disorderly environments
shouldn't cause disorderly processing. The product, whenever obtained, should be invariant
to infrastructure failures unless the specific purpose of the process is to
record infrastructure failures. Of course, the availability of infrastructure
inherently limits the availability of the product. Nevertheless, the availability
of infrastructure is beyond the scope of this discussion.

To limit the scope a little bit further, it is assumed here that whatever records
have been committed by a process will not somehow be damaged by a sudden termination
of the process. Just like an egg is not a chicken, a record is not a process, and
so the reliability of records is beyond the scope of this discussion.

To limit this discussion about process reliability even further, the reliability
of the event processing described below is a separate concern from any programming
errors in the policies, or aggregates, of a process application, errors that may define
pathological behaviour. Unit testing for policies is demonstrated below. Behavioural
programming errors, in process policies and in aggregate methods, are beyond the
scope of this discussion.

.. contents:: :local:


Please note, the library code presented in the example below currently only works
with the library's SQLAlchemy record manager. Django support is planned, Cassandra
support is being considered but will probably be restricted to processes similar
to replication or translation that will write one record for each event notification
received, and use that record as tracking record, event record, and notification
log record, due to the limited atomicity of Cassandra's lightweight transactions.


Process application
-------------------

The library's process application class ``Process`` functions as both an event-sourced projection
(see previous section) and as an event-sourced application. It is a subclass of
``SimpleApplication`` that also has notification log readers and tracking records. A process
application also has a policy that defines how the process application responds to domain events
it receives from its notification log readers.

A process application consumes events by reading event notifications from its notification
log readers. The events are retrieved in a reliable order, without race conditions or
duplicates or missing items.

To keep track of its position in the notification log, a process application will create
a new tracking record for each event notification it processes. The tracking records
determine how far the process has progressed through the notification log. Tracking
records are used to set the position of the notification log reader when the process
is commenced or resumed.

A process application will respond to events according to its policy. Its policy might
do nothing in response to one type of event, and it might call an aggregate method in
response to another type of event.

No matter how the policy responds to an event, the process application will write a
tracking record, along with any new event records, in an atomic database transaction.
Because the recording is atomic, the process can proceed atomically.

If some of the new records can't be written, then none are. If anything
goes wrong before all the records have been written, the transaction will rollback, and none
of the records will be written. If none of the records have been written, the process has
not progressed. On the other hand, if the tracking record has been written, then so will
any new event records, and the process will have fully completed an atomic progression.

Furthermore, there can only be one unique tracking record for each notification.
Once the tracking record has been written it can't be written again, and neither can
any new events unfortunately triggered by duplicate calls to aggregate commands (which
may even succeed and which may not be idempotent). If an event can be processed at all,
then it will be processed exactly once.

A ratchet is as strong as its teeth and pawl. Similarly, a process application is
as reliable as the atomicity of its database transactions. The atomicity of the
database transactions guarantees separately the reliability of both the upstream
notification log (teeth) and the downstream tracking records (pawl). The atomicity
of the recording and consumption determines the production as atomic: a continuous
stream of events is processed in discrete, indivisible units. Hence, interruptions
can only cause delays.

System of processes
-------------------

One process application could follow another in a system of processes. One process could
follow two other processes in a slightly more complicated system. A process could simply
follow itself, stepping though state transitions that involve many aggregates. There could
be a vastly complicated system of processes without introducing any systemically emergent
unreliability in the processing of the events (it is "absolutely" reliable, there isn't
somehow a "tolerable" level of unreliability in each process that would eventually
compound into an intolerable level of unreliability in a complicated system of processes).

A number of application processes could be run from a single thread. Alternatively, they
could each have one thread in a single process. Each thread could have its own operating
system process, and each operating system process could run on its own machine. Although
there is parallelism in such a system, this isn't the kind of parallelism that will
allow the system to scale horizontally (adding more machines).

To scale the throughput of a process horizontally, beyond the rate at which
a single sequence can be processed in series, notifications can be partitioned
across many notification logs. Each partition could be processed concurrently.
Hence one application process could usefully and reliably employ many concurrent
operating system processes. Both kinds of parallelism are demonstrated below.

In the example below, a system of process applications is defined independently of
how it may be run. The system of process applications uses a domain model layer with three
aggregates. Each process application is configured to follow others.

The system is firstly run as a single threaded system. Afterwards, the system is run with
both multiprocessing using the default partition and then also with notification logs and
processing partitioned into multiple system partitions.


Kahn process networks
~~~~~~~~~~~~~~~~~~~~~

Since a notification log functions effectively as a durable FIFO buffer, a system of
determinate process applications pulling notifications logs can be recognised as a
`Kahn Process Network <https://en.wikipedia.org/wiki/Kahn_process_networks>`__ (KPN).

Kahn Process Networks are determinate systems. If a system of process applications
happens to involve processes that are not determinate, the system as a whole will
not be determinate, and could be described in more general terms as "dataflow" or
"stream processing".


.. Refactoring
.. ~~~~~~~~~~~

.. Todo: Something about moving from a single process application to two. Migrate
.. aggregates by replicating those events from the notification log, and just carry
.. on.

Orders, reservations, payments
------------------------------

The example below is suggestive of an orders-reservations-payments system.
The system automatically processes new orders by making a reservation, and
then a payment; facts that are registered with the order, as they happen.

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


A ``Reservation`` can be created. A reservation has an ``order_id``.

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


And a ``Payment`` can be made. A payment also has an ``order_id``.

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
to be resilient against both concurrency conflicts and any operational errors.

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

Process applications have a policy, that responds to domain events by executing commands.

In the code below, the Reservations process responds to new orders by creating a
reservation. The Orders process responds to new reservations by setting as order
as reserved. The Payments process responds by making a payment when as orders
is reserved. The Orders process responds to new payments by setting an order as paid.

The library's ``Process`` class is a subclass of the library's ``SimpleApplication`` class.

.. code:: python

    from time import sleep

    from eventsourcing.application.process import Process


    class Orders(Process):
        persist_event_type=Order.Created

        def policy(self, repository, event):
            if isinstance(event, Reservation.Created):
                # Set the order as reserved.
                order = repository[event.order_id]
                assert not order.is_reserved
                order.set_is_reserved(event.originator_id)

            elif isinstance(event, Payment.Created):
                # Set the order as paid.
                order = repository[event.order_id]
                assert not order.is_paid
                order.set_is_paid(event.originator_id)


    class Reservations(Process):
        def policy(self, repository, event):
            if isinstance(event, Order.Created):
                # Create a reservation.
                sleep(0.5)
                return Reservation.create(order_id=event.originator_id)


    class Payments(Process):
        def policy(self, repository, event):
            if isinstance(event, Order.Reserved):
                # Make a payment.
                sleep(0.5)
                return Payment.make(order_id=event.originator_id)

Please note, nowhere in these policies is a call made to the ``__save__()``
method of aggregates, the pending events will be collected and records
committed automatically by the ``Process`` after the ``policy()`` method has
been called.

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
Remember, do not call the ``__save__()`` method of aggregates in a process policy:
pending events will be collected after the ``policy()`` method has returned.

Please note, although it is necessary to return new aggregates, if a policy
retrieves and changes an already existing aggregate, the aggregate does
not need to be returned by the policy to the caller. The ``Process`` can detect
which aggregates were used from the repository, and these aggregates can be
examined for pending events. It isn't necessary to return changed aggregates
for testing purposes, since the test will already have a reference to the
aggregate, because it will have constructed the aggregate before passing it
to the policy, so the test will already be in a good position to check already
existing aggregates are changed by the policy as expected.

The policy should never call aggregate ``__save__()`` methods, because events will not
be committed atomically with the tracking record, and so the processing will not be
reliable. To be reliable, a process application needs to commit events atomically with
a tracking record, and calling ``__save__()`` will commit new events in a separate
transaction. To explain a little bit, in normal use, when new events are retrieved
from an upstream notification log, the ``policy()`` method is called by the
``call_policy()`` method of the ``Process`` class. The ``call_policy()`` method wraps
the process application's aggregate repository with a wrapper that detects which
aggregates are used by the policy, and calls the ``policy()`` method with the events
and the wrapped repository. New aggregates returned by the policy are appended
to this list. New events are collected from this list of aggregates by getting
any (and all) pending events. The records are then committed atomically with the
tracking record. Calling ``__save__()`` will avoid the new events being included
in this mechanism and will spoil the reliability of the process. As a rule, don't
ever call the ``__save__()`` method of new or changed aggregates in a process
application policy. And always use the given ``repository`` to retrieve aggregates,
rather than the original process application's repository (``self.repository``)
which doesn't detect which aggregates were used when your policy was called.

Anyway, here's a test for the orders policy, at least the half that responds to a
``Reservation.Created`` event by setting the order as "reserved". This test shows
how to test a process application policy that should change an already existing
aggregate in response to a specific type of event.

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

Please note, aggregates are segregated within an application. Each
application can only access from its repository the aggregates it
has created. For example, an order aggregate created by the orders
process will not be available in the repositories of the reservations
and the payments applications.

Application state is only propagated between process applications
in a system through notification logs. If one application could
use the aggregates of another application, processing could produce
different results at different times, and in consequence the process
wouldn't be reliable.

In this system, the Orders process, specifically the Order aggregate
combined with the Orders process policy, is more or less equivalent to
"saga", or "process manager", or "workflow", in that it effectively
controls a sequence of steps involving other bounded contexts and
other aggregates, steps that would otherwise perhaps be controlled with a
"long-lived transaction".

.. Except for the definition and implementation of process,
.. there are no special concepts or components. There are only policies and
.. aggregates and events, and the way they are processed in a process application.
.. There isn't a special mechanism that provides reliability despite the rest
.. of the system, each aggregate is equally capable of functioning as a saga object,
.. every policy is capable of functioning as a process manager or workflow.
.. There doesn't need to be a special mechanism for coding compensating
.. transactions. If required, a failure (e.g. to make a payment) can be
.. coded as an event that can processed to reverse previous steps (e.g.
.. to cancel a reservation).

Single threaded system
----------------------

If the ``system`` object is used as a context manager, the process
applications will be setup to work in the current process. Events
will be processed with a single thread of execution, with synchronous
handling of prompts, so that policies effectively call each other
recursively. This avoids concurrency and is useful when developing
and testing a system of process applications.

In the code below, the ``system`` object is used as a context manager.
In that context, a new order is created.

.. code:: python

    with system:
        # Create new Order aggregate.
        order_id = create_new_order()

        # Check the order is reserved and paid.
        repository = system.orders.repository
        assert repository[order_id].is_reserved
        assert repository[order_id].is_paid

The system responds by making a reservation and a payment, facts that are registered
with the order. Everything happens synchronously, in a single thread, so by the time
the ``create_new_order()`` factory has returned, the system has already processed the
order, which can be retrieved from the "orders" repository.


The process applications above could be run in different threads (not
yet implemented).

Multiprocessing system
----------------------

The example below shows the system of process applications running in
different processes on the same node, using the library's ``Multiprocess``
class, which uses Python's ``multiprocessing`` library.

Running the system with multiple operating system processes means the five steps
for processing an order in this example happen concurrently, so that as the payment
is made for one order, the another order might get reserved, whilst a third order is at
the same time created.

With operating system processes, each can run a loop that begins by making a
call to messaging infrastructure for prompts pushed from upstream via messaging
infrastructure. Prompts can be responded to immediately by pulling new
notifications. If the call to get new prompts times out, any new notifications
from upstream notification logs can be pulled anyway, so that the notification
log is effectively polled at a regular interval. The ``Multiprocess`` class
happens to use Redis publish-subscribe to push prompts.

The process applications could all use the same single database, or they
could each use their own database. If the process applications were using
different databases, upstream notification logs would need to be presented
in an API, so that downstream could pull notifications using a remote
notification log object (as discussed in a previous section).

In this example, the process applications use a MySQL database, but it works just
as well with PostgreSQL.

.. code:: python

    import os

    os.environ['DB_URI'] = 'mysql+mysqlconnector://root:@127.0.0.1/eventsourcing'
    #os.environ['DB_URI'] = 'postgresql://username:password@localhost:5432/eventsourcing'


Single partition
~~~~~~~~~~~~~~~~

Before starting the system's operating system processes, let's create a new order aggregate.
The Orders process is constructed so that any ``Order.Created`` events published by the
``create_new_order()`` factory will be persisted.

.. code:: python

    from eventsourcing.application.simple import SimpleApplication

    with Orders(setup_tables=True) as app:

        # Create a new order.
        order_id = create_new_order()

        # Check new order exists in the repository.
        assert order_id in app.repository


The MySQL database tables were created by the code above, because the ``Orders`` process
was constructed with ``setup_tables=True``, which is by default ``False`` in the ``Process``
class.

The code below uses the library's ``Multiprocess`` class to run the ``system``.
It will start one operating system process for each process application, which
gives three child operating system processes.


.. code:: python

    from eventsourcing.application.multiprocess import Multiprocess

    multiprocess = Multiprocess(system)

The system is unpartitioned, the process applications use the default partition.

In the code below, the operating system processes are started by using
the ``multiprocess`` object as a context manager. It calls ``start()`` on
entry and ``close()`` on exit.

The process applications read their upstream notification logs when they
start, so the ``Order.Created`` event is picked up and processed, causing
the flow through the system. Wait for the results by polling the aggregate state.

.. code:: python

    import time

    if __name__ == '__main__':

        # Start multiprocessing system.
        with Orders() as app, multiprocess:

            retries = 50
            while not app.repository[order_id].is_reserved:
                time.sleep(0.1)
                retries -= 1
                assert retries, "Failed set order.is_reserved"

            while retries and not app.repository[order_id].is_paid:
                time.sleep(0.1)
                retries -= 1
                assert retries, "Failed set order.is_paid"


.. Because the orders are created with a second instance of the ``Orders`` process
.. application, rather than e.g. a command process application that is followed
.. by the orders process, there will be contention and conflicts writing to the
.. orders process notification log. The example was designed to cause this contention,
.. and the ``@retry`` decorator was applied to the ``create_new_order()`` factory, so
.. when conflicts are encountered, the operation will be retried and will most probably
.. eventually succeed. For the same reason, the same ``@retry``  decorator is applied
.. the ``run()`` method of the library class ``Process``. Contention is managed successfully
.. with this approach.
..
.. Todo: Change this to use a command logging process application, and have the Orders process follow it.

Multiple partitions
~~~~~~~~~~~~~~~~~~~

Now let's process a batch of orders that is created after the system
has been started. This time, the system will be partitioned across the
process applications. Each process application-partition will run in a
separate operating system process.

Because of the partitioning, many orders can be processed by the
same process application at the same time. Events generated in one partition
will normally be processed in the same partition downstream (by default, an
application reads and writes in the same partition).

Aggregates continue to be segregated within an application (one application can't
access from its repository the aggregates created by another application) but
aggregates created by one application are accessible across all partitions of
that application.

In the example below, there are five partitions and three process applications, which
gives fifteen child operating system processes. All fifteen will share the same database.
Here, partitioning is configured statically.


.. code:: python

    from eventsourcing.utils.uuids import uuid_from_partition_name

    num_partitions = 5

    partition_ids = [uuid_from_partition_name(i) for i in range(num_partitions)]

    multiprocess = Multiprocess(system, partition_ids=partition_ids)


Twenty-five orders are created in each partition, giving one hundred and twenty-five
orders in total. Please note, when creating the new aggregates, the process application
needs to be told which partition to use.

.. code:: python

    multiprocess = Multiprocess(system, partition_ids=partition_ids)

    num_orders_per_partition = 5

    if __name__ == '__main__':

        # Start multiprocessing system.
        with multiprocess:

            # Create some new orders.
            order_ids = []

            for _ in range(num_orders_per_partition):

                for partition_id in partition_ids:

                    with Orders(partition_id=partition_id) as app:

                        order_id = create_new_order()
                        order_ids.append(order_id)

                        multiprocess.prompt_about('orders', partition_id)


            # Wait for orders to be reserved and paid.
            with Orders() as app:
                retries = 10 + 10 * num_orders_per_partition * len(partition_ids)
                for i, order_id in enumerate(order_ids):

                    while not app.repository[order_id].is_reserved:
                        time.sleep(0.1)
                        retries -= 1
                        assert retries, "Failed set order.is_reserved {} ({})".format(order_id, i)

                    while retries and not app.repository[order_id].is_paid:
                        time.sleep(0.1)
                        retries -= 1
                        assert retries, "Failed set order.is_paid ({})".format(i)

                # Calculate timings from event timestamps.
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

In this example, there are no causal dependencies between events in different partitions.
Causal dependencies between events in different partitions could be detected and used to
synchronise the processing of partitions downstream, so that downstream processing of one
partition can wait for an event to be processed in another. The causal dependencies could
be automatically inferred by detecting the originator ID and version of aggregates as they
are retrieved from the wrapped repository. Those events could be examined to see if they
were notified in a different partitions. If so, the originator ID and version of the
last event in each partition could be included in the notification, so that downstream
can wait for the causal dependencies to be processed before processing the causally dependent
notification. Putting causal dependencies within the same partition would allow the partition
to be processed in parallel to the extent that events aren't always causally dependent
on the preceding event in the notification log. (Causal dependencies not implemented, yet.)

The policy's ``sleep(0.5)`` statements ensure each order takes at least one second
to process, and varying the number of partitions and the number of orders demonstrates
even on a machine with only a few cores (e.g. my laptop) that processing is truly concurrent
both across the process applications, and across the partitions of the system.

Without the ``sleep(0.5)`` statements, the system with its five-step process can process
on a small laptop about twenty-five orders per second per partition, approximately 40ms
for each order, with max and average order processing times of approximately 100ms and
180ms for the five steps.

If most business applications process less than one command per second, one system partition
would probably be sufficient for most situations. However, to process spikes in the demand
without increased latency, or if continuous usage gives ten or a hundred times more commands
per second, then the number of partitions could be increased accordingly. Eventually with
this design, the shared database would limit throughput. But since the operations are
partitioned, the database could be scaled vertically in proportion to the number of
partitions. (Scaling like this hasn't been tested, yet.)

Although it isn't possible to start processes on remote hosts using Python's
``multiprocessing`` library, it is possible to run the system with e.g. partitions
0-7 on one machine, partitions 8-15 on another machine, and so on.

The work of increasing the number of partitions, and starting new operating system
processes, could be automated. Also, the cluster scaling could be automated, and
processes distributed automatically across the cluster. Actor model seems like a
good foundation for such automation.


.. Todo: Make option to send event as prompt. Change Process to use event passed as prompt.

.. There are other ways in which the reliability could be relaxed. Persistence could be
.. optional. ...

Actor model system
------------------

An Actor model library, such as `Thespian Actor Library
<https://github.com/kquick/Thespian>`__, could be used to run
a partitioned system of process applications as actors.

A system actor could start a process application-partition actor
when its address is requested, or otherwise make sure there is
one running actor for each process application-partition.

An actor could stop when there are
no new event notifications to process for a perdiod of time.

Actor processes could be automatically distributed across a cluster. The
cluster could auto-scale according to CPU usage (or perhaps network usage).
New nodes could run a container that begins by registering with the actor
system, (unless there isn't one, when it begins an election to become leader?)
and the actor system could run actors on it, reducing the load on other nodes.

Prompts from one process application-partition could be sent to another
as actor messages, rather than with a publish-subscribe service. The address
could be requested from the system, and the prompt sent directly.

To aid development and testing, actors could run without any
parallelism, for example with the "simpleSystemBase" actor
system in Thespian.

Partitioning of the system could be automated with actors. A system actor
(started how? leader election? Kubernetes configuration?) could increase or
decrease the number of system partitions, according to the rate at which events
are being added to the system command process, compared to the known (or measured)
rate at which commands can be processed by the system. If there are too many actors
dying from lack of work, then to reduce latency of starting an actor for each event
(extreme case), the number of partitions could be reduced, so that there are enough
events to keep actors alive. If there are fewer partitions than nodes, then some nodes
will have nothing to do, and can be easily removed from the cluster. A machine that
continues to run an actor could be more forcefully removed by killing the remaining
actors and restarting them elsewhere. Maybe heartbeats could be used to detect
when an actor has been killed and needs restarting? Maybe it's possible to stop
anything new from being started on a machine, so that it can eventually be removed
without force.


.. However, it seems that actors aren't a very reliable way of propagating application
.. state. The reason is that actor frameworks will not, in a single atomic transaction,
.. remove an event from its inbox, and also store new domain events, and also write
.. to another actor's inbox. Hence, for any given message that has been received, one
.. or two of those things could happen whilst the other or others do not.
..
.. For example what happens when the actor suddenly terminates after a new domain event
.. has been stored but before the event can be sent as a message? Will the message never be sent?
.. If the actor records which messages have been sent, what if the actor suddenly terminates after
.. the message is sent but before the sending could be recorded? Will there be a duplicate?
..
.. Similarly, if normally a message is removed from an actor's inbox and then new domain
.. event records are made, what happens if the actor suddenly terminates before the new
.. domain event records can be committed?
..
.. If something goes wrong after one thing has happened but before another thing
.. has happened, resuming after a breakdown will cause duplicates or missing items
.. or a jumbled sequence. It is hard to understand how this situation can be made reliable.
..
.. And if a new actor is introduced after the application has been generating events
.. for a while, how does it catch up? If there is a separate way for it to catch up,
.. switching over to receive new events without receiving duplicates or missing events
.. or stopping the system seems like a hard problem.
..
.. In some applications, reliability may not be required, for example with some
.. analytics applications. But if reliability does matter, if accuracy if required,
.. remedies such as resending and deduplication, and waiting and reordering, seem
.. expensive and complicated and slow. Idempotent operations are possible but it
.. is a restrictive approach. Even with no infrastructure breakdowns, sending messages
.. can overrun unbounded buffers, and if the buffers are bounded, then write will block.
.. The overloading can be remedied by implementing back-pressure, for which a standard
.. has been written.
..
.. Even if durable FIFO channels were used to send messages between actors, which would
.. be quite slow relative to normal actor message sending, unless the FIFO channels were
.. written in the same atomic transaction as the stored event records, and removing the
.. received event from the in-box, in other words, the actor framework and the event
.. sourcing framework were intimately related, the process wouldn't be reliable.
..
.. Altogether, this collection of issues and remedies seems exciting at first but mostly
.. inhibits confidence that the actor model offers a simple, reliable, and maintainable
.. approach to propagating the state of an application. It seems like a unreliable
.. approach for projecting the state of an event sourced application, and therefore cannot
.. be the basis of a reliable system that processes domain events by generating other
.. domain events. Most of the remedies each seem much more complicated than the notification
.. log approach implemented in this library.
..
.. It may speed a system to send events as messages, and if events are sent as messages
.. and they happen to be received in the correct order, they can be consumed in that way,
.. which should save reading new events from the database, and will therefore help to
.. avoid the database bottlenecking event propagation, and also races if the downstream
.. process is reading notifications from a lagging database replica. But if new events are generated
.. and stored because older events are being processed, then to be reliable, to underwrite the
.. unreliability of sending messages, the process must firstly produce reliable
.. records, before optionally sending the events as prompts. It is worth noting that sending
.. events as prompts loads the messaging system more heavily that just sending empty prompts,
.. so unless the database is a bottleneck for reading events, then sending events as
.. messages might slow down the system (sending events is slower than sending empty prompts
.. when using multiprocessing and Redis on a laptop).
..
.. The low-latency of sending messages can be obtained by pushing empty prompts. Prompts could
.. be rate limited, to avoid overloading downstream processes, which wouldn't involve any loss
.. in the delivery of events to downstream processes. The high-throughput of sending events as
.. messages directly between actors could help avoid database bandwidth problems. But in case
.. of any disruption to the sequence, high-accuracy in propagating a sequence of events can be
.. obtained, in the final resort if not the first, by pulling events from a notification log.

Although propagating application state by sending events as messages with actors doesn't
seem to offer a reliable way of projecting the state of an event-sourced application, actors
do seem like a great way of orchestrating a system of event-sourced process applications. The "based
on physics" thing seems to fit well with infrastructure, which is inherently imperfect.
We just don't need by default to instantiate unbounded nondeterminism for every concern
in the system. But since actors can fail and be restarted automatically, and since a process
application needs to be run by something. it seems that an actor and process process
applications-partitions go well together. The process appliation-actor idea seems like a
much better idea that the aggregate-actor idea. Perhaps aggregates could also usefully be actors,
but an adapter would need to be coded to process messages as commands, to return pending events as
messages, and so on, to represent themselves as message, and so on. It can help to have many
threads running consecutively through an aggregate, especially readers. The consistency of the
aggregate state is protected with optimistic concurrency control. Wrapping an aggregate as
an actor won't speed things up, unless the actor is persistent, which uses resources. Aggregates
could be cached inside the process application-partition, especially if it is know that they will
probably be reused.

.. Todo: Method to fastforward an aggregate, by querying for and applying new events?

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
could be handled by calling commands on aggregates. If callbacks might be retried,
perhaps because the handler crashes after successfully calling a command but before
returning successfully to the caller, unless the callbacks are also tracked (with
exclusive tracking records written atomically with new event and notification records)
the aggregate commands will need to be idempotent, or otherwise guarded against duplicate
callbacks. Such an integration could be implemented as a separate "push-API adapter"
process, and it might be useful to have a generic implementation that can be reused,
with documentation describing how to make such an integration reliable, however the
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

.. Todo: Something about deleting old tracking records automatically.
