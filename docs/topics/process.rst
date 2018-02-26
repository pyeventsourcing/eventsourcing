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


Process
-------

The library class ``Process`` can be used to define an application process. It is
a subclass of the library's ``SimpleApplication`` class.

.. code:: python

    from eventsourcing.application.process import Process


The example below is suggestive of an orders-reservations-payments system. The
system automatically processes new orders by making a reservation, and
automatically makes a payment whenever an order is reserved.

Firstly, event sourced aggregates are defined, for "order", "reservation", and "payment".

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

        def reserved(self):
            self.__trigger_event__(Order.Reserved)

        class Reserved(Event):
            def mutate(self, order):
                order.is_reserved = True

        def paid(self):
            self.__trigger_event__(self.Paid)

        class Paid(Event):
            def mutate(self, order):
                order.is_paid = True

    def create_new_order():
        order = Order.__create__()
        order.__save__()
        return order.id


    class Reservation(AggregateRoot):
        def __init__(self, order_id, **kwargs):
            super(Reservation, self).__init__(**kwargs)
            self.order_id = order_id

        class Event(AggregateRoot.Event):
            pass

        class Created(Event, AggregateRoot.Created):
            pass


    class Payment(AggregateRoot):
        def __init__(self, order_id, **kwargs):
            super(Payment, self).__init__(**kwargs)
            self.order_id = order_id

        class Event(AggregateRoot.Event):
            pass

        class Created(Event, AggregateRoot.Created):
            pass


With the aggregates, the policies of the process can be defined.
In general, policies respond to domain events by executing commands
on aggregates.

.. code:: python

    def orders_policy(process, event):
        unsaved_aggregates = []
        causal_dependencies = []

        if isinstance(event, Reservation.Created):
            # Set order as reserved.
            order = process.repository[event.order_id]
            order.reserved()
            unsaved_aggregates.append(order)

        elif isinstance(event, Payment.Created):
            # Set order as paid.
            order = process.repository[event.order_id]
            order.paid()
            unsaved_aggregates.append(order)

        return unsaved_aggregates, causal_dependencies


    def reservations_policy(process, event):
        unsaved_aggregates = []
        causal_dependencies = []

        if isinstance(event, Order.Created):
            # Create a reservation.
            reservation = Reservation.__create__(order_id=event.originator_id)
            unsaved_aggregates.append(reservation)

        return unsaved_aggregates, causal_dependencies


    def payments_policy(process, event):
        unsaved_aggregates = []
        causal_dependencies = []

        if isinstance(event, Order.Reserved):
            # Create a payment.
            payment = Payment.__create__(order_id=event.originator_id)
            unsaved_aggregates.append(payment)

        return unsaved_aggregates, causal_dependencies


With the policies, the processes can be defined. They can be
configured to follow each other. At least, the orders and the
reservations processes follow each other. The payments and
the orders processes also follow each other. However, the
payments process does not follow the reservations process.

.. Todo: Have a simpler example that just uses one process,
.. instantiated without subclasses. Then defined these processes
.. as subclasses, so they can be used in this example, and then
.. reused in the operating system processes.

.. code:: python

    # Define processes, each uses its own in-memory database.
    orders = Process('orders',
        policy=orders_policy,
        persist_event_type=Order.Event,
    )

    reservations = Process('reservations',
        policy=reservations_policy,
        persist_event_type=Reservation.Event,
    )

    payments = Process('payments',
        policy=payments_policy,
        persist_event_type=Payment.Event,
    )

    # Configure followers.
    orders.follow('reservations', reservations.notification_log)
    orders.follow('payments', payments.notification_log)
    reservations.follow('orders', orders.notification_log)
    payments.follow('orders', orders.notification_log)


Having set up the system of processes, we can run the system by
publishing an event that it responds to. In the code below,
a new order is created. The system responds by making a
reservation and a payment, facts that are registered with
the order.

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

The processes defined above could run in different threads in a single process.
Those threads could run in different processes on a single node. Those process
could run on different nodes in a network.

Each thread could run a loop that makes a call for prompts pushed via
messaging infrastructure. The prompts can be responded to be pulling
from the prompting channel. The call for new messages can timeout,
and the timeout can be handled by pulling any new notifications from
all upstream notification logs, so that effectively the notification log
is polled at a regular interval whenever there are no prompts.

The process applications could all use the same single database, or they
could each use their own database. If the process applications of a system
use different databases, they can still read each other's notification
log object.

Using multiple operating system processes is similar to multi-threading
in a single process. Multiple operating system processes could share
the same database, just not the same in-memory database. They could also
use different databases, even in an memory database, but its notification
log would need to be presented in an API and its readers would need to
use a remote notification log object to pull notifications from the API.

The example below shows a system with multiple operating system processes.
All the application processes share a single MySQL database.

.. code:: python

    import os

    os.environ['DB_URI'] = 'mysql://root:@127.0.0.1/eventsourcing'


Redis is used to publish prompts, so downstream can pull new notifications without polling latency.

.. code:: python

    import redis

    r = redis.Redis()


In this system, each application process runs in its own operating system process.

.. code:: python

    from eventsourcing.application.multiprocess import OperatingSystemProcess

    # Setup the system with multiple operating system processes.
    orders = OperatingSystemProcess(
        process_name='orders',
        process_policy=orders_policy,
        process_persist_event_type=Order.Event,
        upstream_names=['reservations', 'payments'],
    )

    reservations = OperatingSystemProcess(
        process_name='reservations',
        process_policy=reservations_policy,
        process_persist_event_type=Reservation.Event,
        upstream_names=['orders'],
    )

    payments = OperatingSystemProcess(
        process_name='payments',
        process_policy=payments_policy,
        process_persist_event_type=Payment.Event,
        upstream_names=['orders'],
    )


An ``if __name__ == 'main'`` block is required by the multiprocessing
library to distinguish parent process code from child process code.

.. code:: python

    # Multiprocessing "parent process" code block.

    if __name__ == '__main__':

Start the operating system processes.

.. code:: python


        # Start operating system processes.
        orders.start()
        reservations.start()
        payments.start()


.. Todo: Find out why we timeout waiting for subscribers if the create_new_order code is moved below the following.

A process application object can be used to create the
database tables for storing events and tracking records.

.. code:: python

        app = Process(name='orders', policy=None, persist_event_type=Order.Event)

        order_id = create_new_order()

        assert order_id in app.repository


Wait for followers to subscribe.

.. code:: python

        p = r.pubsub()
        p.subscribe('orders')
        assert p.get_message(timeout=5)
        assert p.get_message(timeout=5)
        assert p.get_message(timeout=5)


An event was persisted by the simple application object, but a prompt hasn't been
published. We could wait for followers to poll, but we can save time by publishing
a prompt. So prompt all channel subscribers to pull notifications from the orders application.

By prompting followers of the orders process, the reservations system will
immediately pull the ``Order.Created`` event from the orders process's notification
log, and its policy will cause it to create a reservation object, and so on until
the order is paid.

.. code:: python

        r.publish('orders', '')


Wait for the results. The aggregate state can be polled. We could also pull notifications.

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


Do it again.

.. code:: python

        # Create a new order.
        order2_id = create_new_order()
        assert order2_id in app.repository

        retries = 100
        while not app.repository[order2_id].is_reserved:
            time.sleep(0.1)
            retries -= 1
            assert retries, "Failed set order.is_reserved"

        while retries and not app.repository[order2_id].is_paid:
            time.sleep(0.1)
            retries -= 1
            assert retries, "Failed set order.is_paid"


The system's operating system processes can be terminated by sending a "kill" message.

.. code:: python


        # Clean up.
        app.close()
        r.publish('orders', 'KILL')
        r.publish('reservations', 'KILL')
        r.publish('payments', 'KILL')

        print("Joining...")

        orders.join(timeout=10)
        reservations.join(timeout=10)
        payments.join(timeout=10)

        if orders.is_alive or reservations.is_alive or payments.is_alive:
            orders.terminate()
            reservations.terminate()
            payments.terminate()


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
