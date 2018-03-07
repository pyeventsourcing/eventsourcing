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
be reliable.

.. contents:: :local:

Process application
-------------------

The library's process class, ``Process``, functions as both a projection and as an
event-sourced application. It is a subclass of ``SimpleApplication`` that also
has a notification log reader and tracking records, and a policy that defines
how to use application services when responding to event notifications.

It will consume events by reading event notifications from a notification log reader.
The events are retrieved in a reliable order, without race conditions or duplicates.
To keep track of its position in the notification log, the process will create
a new tracking record for each notification.

It will respond to events according to its policy. Its policy might do nothing in
response to one type of event, and it might call an aggregate method in response
to another type of event.

It will write the tracking record along with any new event records in an atomic
database transaction. The tracking records determine how far the process has progressed
through the notification log. They are used to set the position of the notification log
reader when the process is resumed.

Most importantly, if some of the new records can't be written, then none are. If anything
goes wrong with the infrastructure before the records are committed, the transaction will
fail, and so long as the transaction is atomic, none of the records will be written.

If the tracking record has been written, the process has progressed, otherwise it hasn't.

Furthermore, there can only be one unique tracking record for each notification.
Once the tracking record has been written it can't be written again. So if an event can be
processed at all, then it will be processed exactly once. Whatever the behaviours of the
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
emergent unreliability in the processing of the events (it is "absolutely" reliable,
there isn't somehow a "tolerable" level of unreliability in each process that would eventually
compound into an intolerable level of unreliability in a complicated system of processes).

A number of application processes could be run from a single thread. Alternatively, they
could each have one thread in a single process. Each thread could have its own operating
system process, and each operating system process could run on its own machine. Although
there is parallelism in such a system, this isn't the kind of parallelism that will
allow the system to be scaled horizontally.

To scale the throughput of a process horizontally, beyond the rate at which
a single sequence can be processed in series, notifications could be divided
across many notification logs. Casual dependencies between events in different
notification logs can be automatically inferred (from the aggregates used by
the policy of the process). Hence one application process could usefully and reliably
employ many concurrent operating system processes (the library doesn't support this yet).

In the example below, a system of process applications is defined independently of its
deployment with threads, or multiple operating system processes, or network nodes. It is
then started as a single thread. And later it is also started as multiple operating
system processes.


Kahn process networks
~~~~~~~~~~~~~~~~~~~~~

Since a notification log functions effectively as a durable FIFO buffer, a system of
determinate process applications pulling notifications logs can be recognised as a
`Kahn Process Network <https://en.wikipedia.org/wiki/Kahn_process_networks>`__ (KPN).

Kahn Process Networks are determinate systems. If a system of process applications
happens to involve processes that are not determinate, the system as a whole will
not be determinate, and could be described in more general terms as "dataflow" or
"stream processing". However, in these cases, it may help that other components
are determinate.


Orders, reservations, payments
------------------------------

The example below is suggestive of an orders-reservations-payments system.
The system automatically processes new orders by making a reservation and
then a payment.

Domain model
~~~~~~~~~~~~

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

Process applications
~~~~~~~~~~~~~~~~~~~~

The processes of the orders-reservations-payments system have
policies that respond to domain events by executing commands.

In the code below, the Orders process responds to new reservations
by setting the order as reserved. The Reservations process responds
to new orders by creating a reservation. The Orders process responds
to new payments by setting the order as paid. And the Payments
process responds to orders being reserved by making a payment.

The library's ``Process`` class is a subclass of the library's ``SimpleApplication`` class.

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

The process class policies are easy to test.

.. code:: python

    # Prepare fake repository.
    order = Order(id=1)
    fake_repository = {order.id: order}

    # Construct the payments process.
    with Payments() as process:

        # Check policy makes payment whenever order is reserved.
        event = Order.Reserved(originator_id=order.id, originator_version=1)
        payment = process.policy(fake_repository, event)
        assert isinstance(payment, Payment), payment
        assert payment.order_id == order.id

The Orders process, specifically the Order aggregate combined with the
Orders process policy, is more or less equivalent to "saga", or "process
manager", or "workflow", in that it effectively controls a sequence of
steps involving other bounded contexts and aggregates, steps that would
otherwise perhaps be controlled with a "long-lived transaction".

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

System of processes
~~~~~~~~~~~~~~~~~~~

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
which can be retried from the "orders" repository.

.. code:: python

    with system:
        # Create new Order aggregate.
        order_id = create_new_order()

        # Check the order is reserved and paid.
        repository = system.orders.repository
        assert repository[order_id].is_reserved
        assert repository[order_id].is_paid


Multiprocessing system
----------------------

The process applications above could be run in different threads (not
yet implemented). Alternatively, they run in different processes on a
single node (see below). Those process could run on different nodes in
a network (not yet implemented). The example below shows the process
applications running in different processes on the same node, using
the library's ``Multiprocess`` class, which uses Python's ``multiprocessing``
library.

With multiple threads or operating system processes, each could run a loop that
begins by making a call to messaging infrastructure for prompts pushed from upstream
via messaging infrastructure. Prompts can be responded to immediately
by pulling new notifications. If the call to get new prompts times out,
any new notifications from upstream notification logs can be pulled, so
that the notification log is effectively polled at a regular interval
whenever no prompts are received. The ``Multiprocess`` class uses Redis
publish-subscribe to push prompts.

The process applications could all use the same single database, or they
could each use their own database. If different process applications of a system
are running in the same operating system process, they can use each other's
notification log object (and repository object). Otherwise, the notification
logs (and aggregates) may need to be presented in an API and downstream processes
would need to pull notifications from an upstream API. In this example, the
processes applications use the same database.

The example below shows a system with multiple operating system processes.
All the application processes share one MySQL database. The example works
just as well with PostgreSQL.

.. code:: python

    import os

    os.environ['DB_URI'] = 'mysql+mysqlconnector://root:@127.0.0.1/eventsourcing'
    #os.environ['DB_URI'] = 'postgresql://username:password@localhost:5432/eventsourcing'


Before starting the system's operating, let's create a new Order. The database tables
will be created when the Orders process is constructed, because ``setup_tables=True``.
The Orders process will store the ``Order.Created`` event that is published by the
``create_new_order()`` factory.

.. code:: python

    from eventsourcing.application.simple import SimpleApplication

    with Orders(setup_tables=True) as app:

        # Create a new order.
        order_id = create_new_order()

        # Check new order exists in the repository.
        assert order_id in app.repository


The library's ``Multiprocess`` class can be used to run the ``system``,
with one operating system process for each application process.

.. code:: python

    from eventsourcing.application.multiprocess import Multiprocess

    multiprocess = Multiprocess(system)


Start the operating system processes by using ``multiprocess`` as a
context manager. Wait for the results, by polling the aggregate state.

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


Let's do that again, but with a batch of orders that is created after the system
operating system processes have been started. Below, ``app`` will be working
concurrently with the ``multiprocess`` system. Because there are two instances
of the ``Orders`` process, there may be conflicts writing to the notification
log. That is why the ``@retry`` decorator is applied to the ``create_new_order()``
factory, so that when conflicts are encountered, the operation can be retried.

For the same reason, the ``@retry`` decorator is applied the ``run()`` method
of the process application class, ``Process``. In extreme circumstances, these
retries will be exhausted, and the original exception will be reraised by the
decorator.

.. code:: python

    import datetime

    if __name__ == '__main__':

        # Start multiprocessing system.
        with multiprocess:

            # Start another Orders process, to persist Order.Created events.
            with Orders() as app:

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

Running the system with multiple operating system processes means the different steps
for processing an order happen concurrently, so that as a payment is being made for one
order, the next order might concurrently be being reserved, whilst a third order is at
the same time being created.


Actor model system
------------------

An Actor model library, such as `Thespian Actor Library
<https://github.com/kquick/Thespian>`__, could be used to start the
process applications of a system as actors. Prompts could be sent directly, removing the
need for a publish-subscribe service. Because notifications are pulled from notification logs,
we don't need to worry about resending messages after a crash. Actors could usefully send
error messages. Actors would also provide a way to run process applications
in operating system processes on different nodes in a cluster. Actors could be
run without parallelism using a simple actor system implementation (e.g. "simpleSystemBase"
in Thespian) to ease development and testing. (Running a system of process applications
with actors is not yet implemented.)

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
