==================
Process and system
==================

The most important requirement pursued in this section is to obtain a reliable
process. A process is considered reliable if processing can be resumed after a
breakdown happening at any time, such that the product of the resumed process is
indistinguishable from that which would have been produced without the interruption.

Process can be understood as productive in this way: consumption with recording
determines production. So if the product of a process must be reliable, then its
consumption and its recording must be reliable. If the consumption and the
recording are reliable, then for so long as processing can happen at all, it
will happen in a reliable way. A system of such reliable processes will also
be reliable. If the processes are determinate, then the system will be determinate.

The basic unit of computation in this design is the triad "consume-compute-record".
In particular, the final step when processing a notification is to record a
notification. In this design, pull notifications are pulled and notifications are
recorded. Events are not sent by pushing messages, although pushing prompts may help to
reduce latency.

.. contents:: :local:

Process application
-------------------

The library defines a "process application" with the ``Process`` class, which is a
subclass of ``SimpleApplication``, that functions as both a projection and as an
event-sourced application.

It will consume events by reading event notifications from a notification log reader.
The events are retried in a reliable order, without race conditions or duplicates.
To keep track of the progress through the notification log, the process will create
a new tracking record for each notification.

It will respond to events according to its policy. Its policy might do nothing in
response to one type of event, and it might call an aggregate method in response
to another type of event.

It will write the tracking record along with any new event records, in an atomic
database transaction. The tracking records determine how far the process has progressed
through the notification log (they are used to set the position of the notification log
reader when the process is resumed).

Most importantly, if some of the new records can't be written, then none are. If anything
goes wrong with the infrastructure before the records are committed, the transaction will
fail, and so long as the transaction is atomic, none of the records will be written. If
the tracking record has been written, the process has progressed, otherwise it hasn't.

There can only be one unique tracking record for each notification, once the
tracking record has been written it can't be written again. So if an event can be
processed then it will be processed exactly once. Whatever the behaviours of the
aggregates and the policies of a process, including pathological behaviours such as
infinite loops or deadlocks, the processing of those behaviours will be equally reliable.
Just as a ratchet is as reliable as its pawl, a process application is as reliable as
its database transactions.


System of processes
-------------------

One such process could follow another in a system of processes. One process could follow two
other processes in a slightly more complicated system. A process could simply follow
itself, stepping though state transitions that involve many aggregates. There could
be a vastly complicated system of processes without introducing any systemically
emergent unreliability in the processing of the events (there isn't a "tolerable"
level of error in each process that would eventually compound into an intolerable
level of error in a complicated system).

A number of application processes could be run from a single thread. They could also
have one thread each. Each thread could have its own operating system process, and
each operating system process could run on its own machine. A set of such processes
could be prompted to pull new notifications by sending messages. Although there
is parallelism in such a system, this isn't the kind of parallelism that will
allow the system to be scaled horizontally.

A system of processes can be defined without reference to the threads, or operating
system processes, or network nodes, or notification log partitions. The deployment
of the system could then be defined independently of the deployment, and the deployment
can be scaled independently of the system definition.

To scale the throughput of a process horizontally, beyond the rate at which
a single sequence can be processed in series, notifications could be divided
across many notification logs. Casual dependencies between events in different
notification logs can be automatically inferred (from the aggregates used by
the policy of the process). Hence one application process could usefully and reliably
employ many concurrent operating system processes (the library doesn't support this yet).


Kahn process networks
~~~~~~~~~~~~~~~~~~~~~

Since a notification log functions effectively as a durable FIFO buffer, a system of
determinate process applications pulling notifications logs can be recognised as a
`Kahn Process Network <https://en.wikipedia.org/wiki/Kahn_process_networks>`__ (KPN).
If a system happens to involve processes that are not determinate, the system will not be
determinate, and could be described in more general terms as "dataflow" or "stream processing".


Orders, reservations, payments
------------------------------

The example below is suggestive of an orders-reservations-payments system.
The system automatically processes new orders by making a reservation, and
automatically makes a payment whenever an order is reserved.

Event sourced aggregate root classes are defined, the ``Order`` class is
for "orders", the ``Reservation`` class is for "reservations", and the
``Payment`` class is for "payments".


Domain model
~~~~~~~~~~~~

An ``Order`` aggregate can be created. An order
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


A ``Reservation`` can be created, and a ``Payment`` can be made.

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

Process applications
~~~~~~~~~~~~~~~~~~~~

The library's ``Process`` class is a subclass of the library's ``SimpleApplication`` class.

The processes of the orders-reservations-payments system have
policies that respond to domain events by executing commands.

In the code below, the Reservations process responds to new orders by
creating a reservation. The Orders process responds to new reservations
by setting the order as reserved. The Payments process responds to orders
being reserved by making a payment. The Orders process also responds to new
payments by setting the order as paid.

.. code:: python

    from eventsourcing.application.process import Process


    class Orders(Process):
        persist_event_type=Order.Event

        def policy(self, repository, event):

            if isinstance(event, Reservation.Created):
                reservation = repository[event.originator_id]
                order = repository[reservation.order_id]
                order.set_is_reserved(reservation.id)

            elif isinstance(event, Payment.Created):
                payment = repository[event.originator_id]
                order = repository[payment.order_id]
                order.set_is_paid(payment.id)


    class Reservations(Process):
        persist_event_type=Reservation.Event

        def policy(self, repository, event):

            if isinstance(event, Order.Created):
                # Get details of the order.
                order = repository[event.originator_id]

                # Create a reservation.
                return Reservation.create(order_id=order.id)


    class Payments(Process):
        persist_event_type=Payment.Event

        def policy(self, repository, event):

            if isinstance(event, Order.Reserved):
                order = repository[event.originator_id]
                return Payment.make(order_id=order.id)


The Orders process, specifically the Order aggregate combined with the
Orders process policy, is more or less equivalent to "saga", or "process
manager", or "workflow", in that it effectively controls a sequence of
steps involving other bounded contexts and aggregates, steps that would
otherwise perhaps be controlled with a "long-lived transaction".

The difference is that, here, there are only policies and aggregates, and
the way they are processed. There isn't a special mechanism that provides
reliability despite the system, each aggregate is equally capable of
functioning as a saga object, every policy is capable of functioning as
a process manager or workflow. There doesn't need to be a special mechanism
for coding compensating transactions. If required, a failure (e.g. to make
a payment) can be coded as an event that can processed to reverse previous
steps (e.g. to cancel a reservation).

Third-party systems that provide a server API that you need to call can be
integrated by processing events by calling the APIs. Callbacks that you need
to support can be handled by calling commands on aggregates. It could be
implemented as a separate process. (The library doesn't currently have any
"push-API adapter" process classes).

System of processes
~~~~~~~~~~~~~~~~~~~

A system can now be defined by describing the connections between the
processes in the system.

The library's ``System`` class can be constructed with sequences of
process classes, that show which process follows which other process
in the system. For example, the sequence (A, B, C) shows that B follows A,
and C follows B. The sequence (A, A) shows that A follows A.
The sequence (A, B, A) shows that B follows A, and A follows B.
The sequences ((A, B, A), (A, C, A)) is equivalent to (A, B, A, C, A).

In this example, the orders and the reservations processes need to
follow each other. Also the payments and the orders processes need
to follow each other. There is no direct relationship between
reservations and payments.

.. code:: python

    from eventsourcing.application.process import System


    system = System(
        (Orders, Reservations, Orders),
        (Orders, Payments, Orders),
    )


The system definition can used directly to setup a single threaded system.

.. code:: python

    system.setup()


Having set up a system of processes, we can publish an
event that it responds to, for example an ``Order.Created``
event.

In the code below, a new order is created. The system responds
by making a reservation and a payment, facts that are registered
with the order. Everything happens synchronously in a single
thread, so by the time the ``create_new_order()`` factory
has returned, the system has already processed the order.

.. code:: python


    # Create new Order aggregate.
    order_id = create_new_order()

    # Check the order is reserved and paid.
    repository = system.orders.repository
    assert repository[order_id].is_reserved
    assert repository[order_id].is_paid


The system can be closed, which closes all the system's process applications.

.. code:: python

    # Clean up.
    system.close()


The system above runs in a single thread, but it could also be distributed.


Distributed system
------------------

The application processes above could be run in different threads in a
single process. Those threads could run in different processes on a
single node. Those process could run on different nodes in a network.

If there are many threads, each thread could run a loop that begins by
making a call to messaging infrastructure for prompts pushed from upstream
via messaging infrastructure. Prompts can be responded to immediately
by pulling new notifications. If the call to get new prompts times out,
any new notifications from upstream notification logs can be pulled, so
that the notification log is effectively polled at a regular interval
whenever no prompts are received.

The process applications could all use the same single database, or they
could each use their own database. If the process applications of a system
in the same operating system processes use different databases, they can
still use each other's notification log object.

Using multiple operating system processes is similar to multi-threading,
each process will run a thead that runs a loop. Multiple operating system
processes could share the same database. They could also use different
databases, but then the notification logs may need to be presented in
an API and its readers may need to to pull notifications from the API.

The example below shows a system with multiple operating system processes.
All the application processes share one MySQL database. The example works
just as well with PostgreSQL.

.. code:: python

    import os

    os.environ['DB_URI'] = 'mysql+mysqlconnector://root:@127.0.0.1/eventsourcing'
    #os.environ['DB_URI'] = 'postgresql://username:password@localhost:5432/eventsourcing'


A simple application object can be used to persist ``Order.Created`` events.

.. code:: python

    from eventsourcing.application.simple import SimpleApplication

    with SimpleApplication(name='orders', persist_event_type=Order.Created) as app:

        # Create a new order.
        order_id = create_new_order()

        # Check order exists in the repository.
        assert order_id in app.repository

The library's ``Multiprocess`` class can be used to run the ``system``,
with one operating system process for each application process.

.. code:: python

    from eventsourcing.application.multiprocess import Multiprocess

    multiprocess = Multiprocess(system)


An ``if __name__ == '__main__'`` block is required for the multiprocessing
library to distinguish parent process code from child process code.

By prompting the system processes, the reservations system will
immediately pull the ``Order.Created`` event from the orders
notification log, and its policy will cause it to create a
reservation object, and so on until the order is paid.

Start the operating system processes (uses the multiprocessing library).
Wait for the results, by polling the aggregate state.

.. code:: python

    import time

    if __name__ == '__main__':

        # Start multiprocessing system.
        with multiprocess:

            retries = 100
            while not app.repository[order_id].is_reserved:
                time.sleep(0.1)
                retries -= 1
                assert retries, "Failed set order.is_reserved"

            while retries and not app.repository[order_id].is_paid:
                time.sleep(0.1)
                retries -= 1
                assert retries, "Failed set order.is_paid"


Let's do that again, but with a batch of orders. Below, ``app`` will be working
concurrently with the ``orders`` process that is running in the operating
system process that was started in the previous step. The ``reservations``
and the ``payments`` process will also be processing concurrently with
the ``orders`` process. Because there are two instances of the ``Orders``
process, each may make changes at the same time to the same aggregates, and
there may be conflicts writing to the notification log. Since the conflicts
will causes database transactions to rollback, and commands to be restarted,
it isn't a very good design, but this bad design helps to demonstrate the
processing of the system is reliable.

Please note, the ``retry`` decorator is applied to the ``create_new_order()``
factory, so that when conflicts are encountered, the operation can be retried.
For the same reason, the ``@retry`` decorator is applied the ``run()`` method
of the process application class, ``Process``. In extreme circumstances, these
retries will be exhausted, and the original exception will be reraised by the
decorator. Obviously, if that happened in this example, the ``create_new_order()``
call would fail, and so the code would terminate. But the ``OperatingSystemProcess``
class has a loop that is robust to normal exceptions, and so if the application
process ``run()`` method exhausts its retries, the operating system process loop
will continue, calling the application indefinitely until the operating system
process is terminated.

.. code:: python

    import datetime

    if __name__ == '__main__':

        # Start multiprocessing system.
        with multiprocess:

            # Start simple 'orders' application.
            with SimpleApplication(name='orders', persist_event_type=Order.Created) as app:

                # Start timing duration.
                started = datetime.datetime.now()

                # Create some new orders.
                num = 25
                order_ids = []
                for _ in range(num):
                    order_id = create_new_order()
                    order_ids.append(order_id)
                    multiprocess.prompt()

                # Wait for orders to be reserved and paid.
                retries = num * 10
                for i, order_id in enumerate(order_ids):

                    while not app.repository[order_id].is_reserved:
                        time.sleep(0.1)
                        retries -= 1
                        assert retries, "Failed set order.is_reserved {} ({})".format(order_id, i)

                    while retries and not app.repository[order_id].is_paid:
                        time.sleep(0.1)
                        retries -= 1
                        assert retries, "Failed set order.is_paid ({})".format(i)

                # Print rate of order processing.
                duration = (datetime.datetime.now() - started).total_seconds()
                rate = float(num) / duration
                print("Orders system processed {} orders in {:.2f}s at rate of {:.2f} orders/s".format(
                    num, duration, rate
                ))

Using the Python ``multiprocessing`` library is one way to deploy the application process
system. Alternatively, an Actor framework could be used to start and monitor operating system
processes running the process applications, and send the prompts. An Actor framework might also
provide a way to run multiple processes on different nodes in a cluster.

Actor framework
---------------

Todo: Actor framework deployment of system.

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
