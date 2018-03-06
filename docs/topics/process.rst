==================
Process and system
==================

Process can be understood as productive in this way: consumption with recording
determines production. If the product of a process must be reliable, then its
consumption and its recording must be reliable. If the consumption and the
recording are reliable, then for so long as processing can happen at all, it
will happen in a reliable way.

.. contents:: :local:

Summary
-------

The library's ``Process`` class is a subclass of ``SimpleApplication`` that
effectively functions as both an event-sourced application and an event-sourced
projection. The process application class pulls event notifications in a reliable order
from a notification log reader. The process responds to these events in turn according
to a policy. The policy might do nothing in response to one type of event, and it might
call an aggregate method in response to another type of event. To keep track of the
progress through the notification log, the process will write a new tracking record
for each notification, along with any new event records it triggers, in a single atomic
database transaction. The tracking records determine how far the process has progressed
through the notification log (they are used to set the position of the notification log
reader). Therefore, such a process is as reliable as its database transactions are atomic.

Most importantly, if some of the new records can't be written, then none are. If anything
goes wrong with the infrastructure before the records are committed, the transaction will
simply not be successful, so none of the records will be written. Until the
tracking record has been written, the process effectively doesn't progress. Tracking
records are unique, once the tracking record has been written it can't be
written again, so if an event can be processed then it will be processed exactly once.
Whatever the behaviours of the aggregates and the policies used by a process, the
processing of those behaviours will be reliable.

One such process could follow another, in a system. One process could follow two
other processes in a slightly more complicated system. A process could simply follow
itself, stepping though state transitions that involve many aggregates. There could
be a vastly complicated system of processes without introducing any systemically
emergent unreliability in the processing of the events.

A number of application processes could be run from a single thread. They could also
have one thread each. Each thread could have its own operating system process, and
each operating system process could run on its own machine. A set of such processes
could be prompted to pull new notifications by sending messages. Although there
is parallelism in such a system, this isn't the kind of parallelism that will
allow the system to be scaled horizontally.

To scale the throughput of a process beyond the limit of processing a single sequence
in series, notifications could be distributed across many logs. Casual dependencies
across notification logs can be automatically inferred from the aggregates used by
the policy of the process. Hence one application process could usefully and reliably
employ many concurrent operating system processes (the library doesn't support this yet).

A system of processes can be defined without reference to the threads, or operating
system processes, or network nodes, or notification log partitions. The deployment
of the system could then be defined independently of the deployment, and the deployment
can be scaled independently of the system definition.


Kahn Process Networks
---------------------

A system of process applications that read each other's notifications logs,
can be recognised as a `Kahn Process Network <https://en.wikipedia.org/wiki/Kahn_process_networks>`__ (KPN).
Althoug supercomputers are designed as Kahn Process Networks, and image processing
is often used as an example, Kahn Process Networks are considered to be an under used
model of distributed computation. At the time of writing, there is nothing in `Google Search
<https://www.google.co.uk/search?q=%22Domain+Driven+Design%22+%22Kahn+Process+Network%22>`__
about both "Domain Driven Design" and "Kahn Process Networks". There is only one video on YouTube,
a talk about hardware, `implementing KPNs in silicone <https://www.youtube.com/watch?v=sDuuvyUaIAc>`__.


Application process
-------------------

The library's ``Process`` class is a subclass of the library's ``SimpleApplication`` class.

The example below is suggestive of an orders-reservations-payments system.
The system automatically processes new orders by making a reservation, and
automatically makes a payment whenever an order is reserved.

Event sourced aggregate root classes are defined, the ``Order`` class is
for "orders", the ``Reservation`` class is for "reservations", and the
``Payment`` class is for "payments".

Firstly, an ``Order`` aggregate can be created. Having been created, an order
can be set as reserved, which involves a reservation ID. And having been reserved,
it can be set as paid, which involves a payment ID.

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


The processes are defined with policies that respond
to domain events by executing commands. In the code below, the
Reservations process responds to new orders by creating a reservation.
The Orders process responds to new reservations by setting the order
as reserved. The Payments process responds to orders being reserved
by making a payment. The Orders process also responds to new
payments by setting the order as paid.

.. Todo: Have a simpler example that just uses one process,
.. instantiated without subclasses. Then defined these processes
.. as subclasses, so they can be used in this example, and then
.. reused in the operating system processes.

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

Having defined the processes, we can compose them into a system.

.. .. code:: python
..
..     from eventsourcing.application.process import System
..
..
..     system = System(
..         (Orders, ['reservations', 'payments']),
..         (Reservations, ['orders']),
..         (Payments, ['orders']),
..     )
..
.. Todo: Make everything below work from this system definition.

.. code:: python


    # Construct process applications, each uses the same in-memory database.
    orders = Orders()
    reservations = Reservations(session=orders.session)
    payments = Payments(session=orders.session)


The orders and the reservations processes need to follow each other. Also
the payments and the orders processes need to follow each other. There is
no direct following relationship between reservations and payments.

.. code:: python

    orders.follow('reservations', reservations.notification_log)
    reservations.follow('orders', orders.notification_log)

    orders.follow('payments', payments.notification_log)
    payments.follow('orders', orders.notification_log)

.. Todo: It would be possible for the tracking records of one process to
.. be presented as notification logs, so an upstream process
.. pull information from a downstream process about its progress.
.. This would allow upstream to delete notifications that have
.. been processed downstream, and also perhaps the event records.
.. All tracking records except the last one can be removed. If
.. processing with multiple threads, a slightly longer history of
.. tracking records may help to block slow and stale threads from
.. committing successfully. This hasn't been implemented in the library.

Having set up a system of processes, we can run the system by
publishing an event that it responds to. In the code below,
a new order is created. The system responds by making a
reservation and a payment, facts that are registered with
the order. Everything happens synchronously in a single
thread, so by the time the ``create_new_order()`` factory
has returned, the system has already processed the order.

.. code:: python


    # Create new Order aggregate.
    order_id = create_new_order()

    # Check the order is reserved and paid.
    assert orders.repository[order_id].is_reserved
    assert orders.repository[order_id].is_paid


The system can be closed by closing all the processes.

.. code:: python

    # Clean up.
    orders.close()
    reservations.close()
    payments.close()


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


In this system, each application process runs in its own operating system process.
The library's ``OperatingSystemProcess`` class extends ``multiprocessing.Process``.
When is starts running, it constructs an application proces object, subscribes
for upstream prompts, and loops on getting prompts from messsaging infrastructure.

It uses Redis, but it could use any publish-subscribe mechanism. We could also
use an actor framework to start operating system processes and send prompt
messages directly to followers that have subscribed (just didn't get that far yet).

.. code:: python

    from eventsourcing.application.multiprocess import OperatingSystemProcess

    orders = OperatingSystemProcess(
        application_process_class=Orders,
        upstream_names=['reservations', 'payments'],
    )

    reservations = OperatingSystemProcess(
        application_process_class=Reservations,
        upstream_names=['orders'],
    )

    payments = OperatingSystemProcess(
        application_process_class=Payments,
        upstream_names=['orders'],
    )


This example uses Redis to publish and subscribe to prompts.

.. code:: python

    import redis

    r = redis.Redis()


An ``if __name__ == 'main'`` block is required by the multiprocessing
library to distinguish parent process code from child process code.

.. code:: python

    # Multiprocessing "parent process" code block.

    if __name__ == '__main__':


Start the operating system processes (uses the multiprocessing library).

.. code:: python


        try:

            # Start operating system processes.
            orders.start()
            reservations.start()
            payments.start()


A process application object can be used in the parent process to persist
Order events. The ``Orders`` process application class can be used. It might
be better to have had a command logging process, and have the orders process
follow the command process. Then, each application would be running in just
one thread. However, in this example, two instances of the orders process
are running concurrently, which means the library needs to be robust against
notification log conflicts and branching the state of aggregate (which it is).

.. code:: python

            app = Process(name='orders', policy=None, persist_event_type=Order.Event)


This ``app`` will be working concurrently with the ``orders`` process
that is running in the operating system process that was started in the
previous step. Because there are two instances of the ``Orders`` process,
each may make changes at the same time to the same aggregates, and
there may be conflicts writing to the notification log. Since the conflicts
will causes database transactions to rollback, and commands to be restarted,
it isn't a very good design, but it still works because the process is reliable.

The ``retry`` decorator is applied to the ``create_new_order()`` factory, so
that when conflicts are encountered, the operation can be retried. For the
same reason, the ``@retry`` decorator is applied the ``run()`` method
of the process application class, ``Process``. In extreme circumstances, these
retries will be exhausted, and the original exception will be reraised by the
decorator. Obviously, if that happened in this example, the ``create_new_order()``
call would fail, and so the code would terminate. But the ``OperatingSystemProcess``
class has a loop that is robust to normal exceptions, and so if the application
process ``run()`` method exhausts its retries, the operating system process loop
will continue, calling the application indefinitely until the operating system
process is terminated.

.. code:: python

            order_id = create_new_order()

            assert order_id in app.repository


An event was persisted by the simple application object, but a prompt hasn't been
published. We could wait for followers to poll, but we can save time by publishing
a prompt.

.. code:: python

            # Wait for the two followers to subscribe.
            while r.publish('orders', '') < 2:
                pass


By prompting followers of the orders process, the reservations system will
immediately pull the ``Order.Created`` event from the orders process's notification
log, and its policy will cause it to create a reservation object, and so on until
the order is paid.


Wait for the results, by polling the aggregate state.

.. code:: python

            import time

            retries = 100
            while not app.repository[order_id].is_reserved:
                time.sleep(0.1)
                retries -= 1
                assert retries, "Failed set order.is_reserved"

            while retries and not app.repository[order_id].is_paid:
                time.sleep(0.1)
                retries -= 1
                assert retries, "Failed set order.is_paid"


Do it again, lots of times.

.. code:: python

            import datetime

            started = datetime.datetime.now()

            # Create some new orders.
            #num = 500
            num = 25
            order_ids = []
            for _ in range(num):
                order_id = create_new_order()
                order_ids.append(order_id)
                r.publish('orders', '')

            retries = num * 10
            #retries = num * 20  # need more time for chaos injection

            for i, order_id in enumerate(order_ids):

                while not app.repository[order_id].is_reserved:
                    time.sleep(0.1)
                    retries -= 1
                    assert retries, "Failed set order.is_reserved {} ({})".format(order_id, i)

                while retries and not app.repository[order_id].is_paid:
                    time.sleep(0.1)
                    retries -= 1
                    assert retries, "Failed set order.is_paid ({})".format(i)

            duration = (datetime.datetime.now() - started).total_seconds()
            rate = float(num) / duration
            print("Orders system processed {} orders in {:.2f}s at rate of {:.2f} orders/s".format(
                num, duration, rate
            ))

The system's operating system processes can be terminated by sending a "kill" message.

.. code:: python

        finally:
            # Clean up.
            r.publish('orders', 'KILL')
            r.publish('reservations', 'KILL')
            r.publish('payments', 'KILL')

            orders.join(timeout=1)
            reservations.join(timeout=1)
            payments.join(timeout=1)

            if orders.is_alive:
                orders.terminate()

            if reservations.is_alive:
                reservations.terminate()

            if payments.is_alive:
                payments.terminate()

            app.close()


The example above uses a single database for all of the processes in the
system, but if the notifications for each process are presented in an API
for others to read remotely, each process could use its own database.


.. Todo: "Instrument" the tracking records (with a notification log?) so we can
.. measure how far behind downstream is processing events from upstream.

.. Todo: Maybe a "splitting" process that has two applications, two
.. different notification logs that can be consumed separately.



Process DSL
~~~~~~~~~~~

The example below is currently just a speculative design idea, not currently supported by the library.

.. code::

    @process(orders_policy)
    def orders():
        reservations() + payments()

    @process(reservations_policy)
    def reservations():
        orders()

    @process(payments_policy)
    def payments():
        orders()
