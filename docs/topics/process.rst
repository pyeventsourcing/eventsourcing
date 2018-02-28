==================
Process and system
==================

In this section, the projections in the previous section are developed
further into "process applications": event sourced applications that both
consume notification logs and call command methods on aggregates, producing
new domain events that are placed in a notification log for others to consume.

Process can be generally understood in this way: consumption with recording
determines production. In other words, if both consumption and recording
are reliable, the process is reliable. A system of reliable processes is
also reliable.

For a process application to be reliable, its consumption of notification
logs and its recording of its projected state must be reliable. Essentially,
a process must both be able to read a notification log and write its records
atomically. The records that track its consumption of notification logs, the
domain events it records, and the new notification log records must be written
together in a single database transaction.

The library's ``Process`` class is defined as a projection that also functions
as an event sourced application. It responds to notifications by calling aggregate
methods, sometimes triggering new events, then writing a new tracking record,
along with any new event and notification records, in a single atomic database
transaction.

If some of the new records can't be written, none are. If something is wrong
with the policy, or with the aggregates, or with the infrastructure, then the
transaction will not be successful, so it will fail, and none of the records
will be written. If the tracking record isn't written, the process doesn't
move forward, as if nothing happened. If an aggregate produces the wrong events,
or the policies make things go around in circles indefinitely, that's behaviour
that will be processed reliably. So long as processing can happen at all, it will
happen in a reliable way. Such a process is as reliable as database transactions.

Such an application process could follow another such application process in a
system. One process could follow two other processes in a slightly more complicated
system. A process could simply follow itself, stepping though state transitions
that involve many aggregates. There could be a vastly complicated system of processes
without introducing any systemically emergent unreliability in the processing
of the events.

A number of application processes could be deployed in a single thread, or with
multiple threads in a single operating system process. Each thread could
have its own operating system process, and each operating system process
could run on its own machine. A set of such processes could be prompted to
pull new notifications by sending messages.

All notifications from an application process could be placed in a single
notification log sequence, and processed in series. To scale throughput
beyond the limits of processing a single sequence, notifications could
be distributed across many logs (with causal dependencies easily inferred from
aggregate IDs and versions involved in generating new events). Hence one
application process could usefully and reliably employ many concurrent operating
system processes.

A system of processes could be defined without reference to threads, operating
system processes, network nodes, or notification log partitions. The deployment
of the system could then be defined and scaled independently (library doesn't
support this yet).


Kahn Process Networks
---------------------

A system of process applications that pull from each other's notifications logs,
can be recognised as a `Kahn Process Network <https://en.wikipedia.org/wiki/Kahn_process_networks>`__ (KPN).
Supercomputers are designed as Kahn Process Networks. In contrast with the unbounded
nondeterminism of messaging systems in general, and the Actor Model in particular,
Kahn Process Networks are deterministic. For the same input history they must always
produce exactly the same output.

Kahn Process Networks appears to be an underused model of distributed computation.
At the time of writing, there is nothing in `Google Search
<https://www.google.co.uk/search?q=%22Domain+Driven+Design%22+%22Kahn+Process+Network%22`__
about "Domain Driven Design" and "Kahn Process Networks". There is only one video on YouTube,
a talk about hardware, `implementing KPNs in silicone <https://www.youtube.com/watch?v=sDuuvyUaIAc>`__.

Maybe KPNs been tried for DDD, and it doesn't work very well. If so, apparently there are no traces online.
However the Agile and LEAN approaches are fundamentally "pull" and not "push", so it
might make good sense for the systems produced by iterative and incremental development
to pull notifications rather than push messages.

It's hard to see how KPNs are included in the common definition and understanding of distributed
computing, that it fundamentally involves `passing messages
<https://en.wikipedia.org/wiki/Distributed_computing>`__, which is understood as pushing messages,
for example AMQP systems or Actor frameworks.

Application process
-------------------

The library class ``Process`` can be used to define an application process.

.. code:: python

    from eventsourcing.application.process import Process

The ``Process`` class is a subclass of the library's ``SimpleApplication`` class.

The example below is suggestive of an orders-reservations-payments system.
The system automatically processes new orders by making a reservation, and
automatically makes a payment whenever an order is reserved.

Event sourced aggregates are defined, for "order", "reservation", and "payment".

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

    from eventsourcing.domain.model.decorators import retry
    from eventsourcing.exceptions import OperationalError, RecordConflictError

    @retry((OperationalError, RecordConflictError), max_attempts=10, wait=0.01)
    def create_new_order():
        order = Order.__create__()
        order.__save__()
        return order.id


    class Reservation(AggregateRoot):
        def __init__(self, order_id, **kwargs):
            super(Reservation, self).__init__(**kwargs)
            self.order_id = order_id

        @classmethod
        def create(cls, order_id):
            return cls.__create__(order_id=order_id)

        class Event(AggregateRoot.Event):
            pass

        class Created(Event, AggregateRoot.Created):
            pass


    class Payment(AggregateRoot):
        def __init__(self, order_id, **kwargs):
            super(Payment, self).__init__(**kwargs)
            self.order_id = order_id

        @classmethod
        def make(self, order_id):
            return self.__create__(order_id=order_id)

        class Event(AggregateRoot.Event):
            pass

        class Created(Event, AggregateRoot.Created):
            pass


There application processes are defined to use the aggregates,
with policies that respond to domain events by executing commands
on aggregates.


.. Todo: Have a simpler example that just uses one process,
.. instantiated without subclasses. Then defined these processes
.. as subclasses, so they can be used in this example, and then
.. reused in the operating system processes.

.. code:: python

    # Define processes, each uses its own in-memory database.
    class Orders(Process):
        persist_event_type=Order.Event

        def policy(self, event):
            unsaved_aggregates = []
            causal_dependencies = []

            if isinstance(event, Reservation.Created):

                # Set order as reserved.
                reservation = self.get_originator(event, use_cache=False)
                order = self.get_originator(reservation.order_id)
                order.set_is_reserved(reservation.id)
                unsaved_aggregates.append(order)

            elif isinstance(event, Payment.Created):
                # Set order as paid.
                payment = self.get_originator(event, use_cache=False)
                order = self.get_originator(payment.order_id)
                order.set_is_paid(payment.id)
                unsaved_aggregates.append(order)

            return unsaved_aggregates, causal_dependencies


    class Reservations(Process):
        persist_event_type=Reservation.Event

        def policy(self, event):
            unsaved_aggregates = []
            causal_dependencies = []

            if isinstance(event, Order.Created):
                # Get details of the order.
                order = self.repository[event.originator_id]

                # Create a reservation.
                reservation = Reservation.create(order_id=order.id)
                unsaved_aggregates.append(reservation)

            return unsaved_aggregates, causal_dependencies


    class Payments(Process):
        persist_event_type=Payment.Event

        def policy(self, event):
            unsaved_aggregates = []
            causal_dependencies = []

            if isinstance(event, Order.Reserved):
                # Get details of the order (alternative method).
                order = self.get_originator(event, use_cache=False)

                # Make a payment.
                payment = Payment.make(order_id=order.id)
                unsaved_aggregates.append(payment)

            return unsaved_aggregates, causal_dependencies


    # Construct process applications, each uses the same in-memory database.
    orders = Orders()
    reservations = Reservations(session=orders.session)
    payments = Payments(session=orders.session)


Configure the orders and the reservations processes to follow
each other. The payments and the orders processes also follow
each other. However, the payments process does not follow the
reservations process.

.. code:: python

    orders.follow('reservations', reservations.notification_log)
    reservations.follow('orders', orders.notification_log)

    orders.follow('payments', payments.notification_log)
    payments.follow('orders', orders.notification_log)


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
whenever there are no prompts. This protects against failed push.

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


Start the operating system processes.

.. code:: python


        try:

            # Start operating system processes.
            orders.start()
            reservations.start()
            payments.start()


.. Todo: Find out why we timeout waiting for subscribers if the create_new_order code is moved below the following.

A process application object can be used in the parent process to persist
the new orders. We reuse the orders process application class, but it might
be better to have a command logging process, and have the orders process
follow the command process. Then each application would be running in just
one thread. However in this example, two instances of the orders process
are running concurrently

.. code:: python

            app = Process(name='orders', policy=None, persist_event_type=Order.Event)


This ``app`` is working concurrently with the ``orders`` process
that is running in the operating system process we just started. That
means when we create orders, we might conflict with notification log entries
written by the other orders process, as it responds to reservations and payments.
The other process may encounter the same kind of conflict.

Conflicts, and also operation errors, can be usefully retried. That is why
the ``retry`` decorator is applied to the ``create_new_order()`` factory, above.
For the same reason the ``@retry`` decorator is applied the ``run()`` method
of the process application class ``Process``. In extreme circumstances, these
retries will be exhausted, and the original exception will be reraised by the
decorator.

.. code:: python

            order_id = create_new_order()

            assert order_id in app.repository


An event was persisted by the simple application object, but a prompt hasn't been
published. We could wait for followers to poll, but we can save time by publishing
a prompt.

By prompting followers of the orders process, the reservations system will
immediately pull the ``Order.Created`` event from the orders process's notification
log, and its policy will cause it to create a reservation object, and so on until
the order is paid.

.. code:: python

            count = 0
            while count < 2:
                count += r.publish('orders', '')


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
            num = 1
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
