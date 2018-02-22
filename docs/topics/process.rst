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

The library class ``Process``, a subclass of ``SimpleApplication``, can be
used to write a scale-independent definition of a system.


.. code:: python

    from eventsourcing.application.process import Process


Example
~~~~~~~

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

        def reserve(self):
            self.__trigger_event__(Order.Reserved)

        class Reserved(Event):
            def mutate(self, order):
                order.is_reserved = True

        def pay(self):
            self.__trigger_event__(self.Paid)

        class Paid(Event):
            def mutate(self, order):
                order.is_paid = True


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
            order.reserve()
            unsaved_aggregates.append(order)

        elif isinstance(event, Payment.Created):
            # Set order as paid.
            order = process.repository[event.order_id]
            order.pay()
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


    # Define processes.
    orders = Process(policy=orders_policy, persist_event_type=Order.Event)
    reservations = Process(policy=reservations_policy, persist_event_type=Reservation.Event)
    payments = Process(policy=payments_policy, persist_event_type=Payment.Event)

    # Follow notification logs.
    reservations.follow(orders.notification_log, 'orders')
    payments.follow(orders.notification_log, 'orders')
    orders.follow(reservations.notification_log, 'reservations')
    orders.follow(payments.notification_log, 'payments')

    # Create new order aggregate.
    order = Order.__create__()
    order.__save__()

    # Check the order is not reserved or paid.
    assert not orders.repository[order.id].is_reserved
    assert not orders.repository[order.id].is_paid

    # Prompt the reservations and order process.
    reservations.run()
    orders.run()

    # Check the order is reserved.
    assert orders.repository[order.id].is_reserved

    # Prompt the payments and order process.
    payments.run()
    orders.run()

    # Check the order has been paid.
    assert orders.repository[order.id].is_paid



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
