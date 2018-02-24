==================
Process and system
==================

In general, process can be defined as productive in this sense: consumption with
recording determines production. In particular, the library's ``Process`` class is
defined as a projection that also functions as an event sourced application. It
responds to notifications by calling aggregate methods, sometimes triggering new
events, then writing a new tracking record along with any new event and notification
records in a single atomic database transaction.

The point is that if some of the new records can't be written, none are. If
something is wrong with the policy, or with the aggregates, or with the
infrastructure, then the transaction will be rolled back, and none of the
records will be written. If the tracking record isn't written, the position doesn't
move, and the processing will have to be tried again. If an aggregate produces
the wrong events, or the policies make things go around in circles indefinitely,
that's behaviour that will be processed reliably, so long as processing can happen at all.
The process, in itself, is as reliable as database transactions.

Such an application process could follow another such process in a system. One process
could follow two other processes in a slightly more complicated system. A process
could simply follow itself, stepping though state transitions that involve
many aggregates. There could be a vastly complicated system of processes
without introducing any systemically emergent unreliability in the processing
of the events.

A number of application processes could be run in a single operating system
process, even with a single thread. They could also be run concurrently
on different nodes in a network. A set of such processes could be pulsed from
a clock, and also prompted by pushing notifications, reducing latency and
avoiding aggressive polling intervals.

To keep things simple, all notifications from an application process can be
placed in a single notification log sequence, and processed in series. To scale
throughput beyond the limits of processing a single sequence, notifications could
be distributed across many logs (with immediate causal dependencies inferred from
the ID and version of the aggregates necessary for processing the notification).
Hence one application process could usefully and reliably employ many concurrent
operating system processes.


Process
-------

The library class ``Process``, a subclass of ``SimpleApplication``, can be
used to write a scale-independent definition of a system.


.. code:: python

    from eventsourcing.application.process import Process


The example below shows an orders-reservations-payments system.


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


############### Remove this before committing

    # Define processes.
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

    orders.follow('reservations', reservations.notification_log)
    orders.follow('payments', payments.notification_log)
    reservations.follow('orders', orders.notification_log)
    payments.follow('orders', orders.notification_log)

    # Create new order.
    order_id = create_new_order()

    # Check the order is reserved and paid.
    assert orders.repository[order_id].is_reserved
    assert orders.repository[order_id].is_paid

    # Clean up.
    orders.close()
    reservations.close()
    payments.close()


Distributed system
------------------

The system above runs in a single thread, but it could be run in multiple-threads in a single process,
as multiple processes on a single node, or on multiple nodes.

Using multiple threads would involve each thread running a loop that either polls for new notifications and sleeps
for a little bit, or works on items its gets in blocking mode from a thread-safe queue. Both could operate at the
same time, so long as contention errors are handled without crashing the loop. The items on the queue would be
prompts added to the queue by a handler subscribed by the application process to receive prompts published to the
library's pub-sub mechanism. The threads could be constructed and started, and sent poison pills and joined to
shutdown the system, in the normal way. The process applications could use the same or different databases. If
process applications use different databases, they won't be able to access the aggregates of the other applications,
which may be desirable but it may also be inconvenient. Using a different database for each process might be
desirable for example if each process is developed by a separate team, and it may improve performance in a system
with a lot of processes.

Using multiple operating system processes is similar to multi-threading in a single process. Each would need to
run a loop, that would poll for notifications and sleep for a little bit, or subscribe and publish prompts to a
pub-sub service. Multiple operating system processes could share the same database, just not the same in-memory
database. They could also use different databases, even in an memory database, but its notification log would need
to be presented in an API and its readers would need to use a remote notification log object.

The example below shows the application processes, defined above, in a system that uses one operating system per
application process to listen for and respond to prompts published to Redis. A MySQL database is shared by the
application processes.

.. code:: python

    import os
    import time

    import redis

    from eventsourcing.application.multiprocess import OperatingSystemProcess

    os.environ['DB_URI'] = 'mysql://username:password@localhost/eventsourcing'
    #os.environ['DB_URI'] = 'postgresql://username:password@localhost:5432/eventsourcing'
    r = redis.Redis()

    if __name__ == '__main__':
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

        app = Process('orders', persist_event_type=Order.Event, policy=None, setup_table=True)

        orders.start()
        reservations.start()
        payments.start()

        with app:
            # Create a new order, and broadcast a prompt.
            position = app.notification_log.get_end_position()
            order_id = create_new_order()

            # Todo: Subscribe to the Prompt and pass the position in the notification log...
            # Make sure the subscribers are setup.
            while not r.publish('orders', ''):
                pass

            # Wait for the results.
            retries = 0
            while retries < 100:
                order = app.repository[order_id]
                if app.repository[order_id].is_reserved:
                    break
                time.sleep(0.1)
                retries += 1
            else:
                assert False

            retries = 0
            while retries < 100:
                order = app.repository[order_id]
                if app.repository[order_id].is_paid:
                    break
                time.sleep(0.1)
                retries += 1
            else:
                assert False

        r.publish('orders', 'KILL')
        r.publish('reservations', 'KILL')
        r.publish('payments', 'KILL')
        time.sleep(0.1)

        orders.join(timeout=12)
        reservations.join(timeout=12)
        payments.join(timeout=12)

        if orders.is_alive or reservations.is_alive or payments.is_alive:
            time.sleep(1)
            orders.terminate()
            reservations.terminate()
            payments.terminate()

        orders.join(timeout=2)
        reservations.join(timeout=2)
        payments.join(timeout=2)




The example above uses a single database for all of the processes in the system, but if the notifications for each
process are presented in an API for others to read remotely, each process could use its own database.


.. Todo: "Splitting" process that has two applications, two different notification logs that can be consumed
.. separately.


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
