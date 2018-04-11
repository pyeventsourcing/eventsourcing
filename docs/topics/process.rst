==================
Process and system
==================

This section is about process applications. A process application is
a projection that also work as an event sourced application. A system
of process applications can be constructed by placing the process
applications in a pipeline.

Reliability is the most important concern in this section. A process is considered to
be reliable if its product is entirely unaffected by a sudden termination of the process
happening at any time, except in being delayed. The other important concerns are
scalability and maintainability.

The only trick is remembering consumption with recording determines production.
In particular, if the product of the process must be reliable, then the consumption
and the recording must be reliable.

This definition of the reliability of a process ("safety") doesn't include availability
("liveness"). Infrastructure unreliability may cause processing delays. But disorderly
environments shouldn't cause disorderly processing.


.. To limit this discussion even further, any programming errors in the policies or
.. aggregates of a process that may inadvertently define pathological behaviour are
.. considered to be a separate concern.

.. contents:: :local:


Please note, the library code presented in the example below currently only works
with the library's SQLAlchemy record manager. Django support is planned. Cassandra
support is being considered but will probably be restricted to processes similar
to replication or translation that will write one record for each event notification
received, and use that record as tracking record, event record, and notification
log record, due to the limited atomicity of Cassandra's lightweight transactions.


Overview
========

Process application
-------------------

The library's process application class ``Process`` functions both as an
event-sourced projection (see previous section) and as an event-sourced
application. It is a subclass of ``SimpleApplication`` that also has
notification log readers and tracking records.

A process application also has a policy that defines how the process application
responds to the domain events it will receive from its notification log readers.


Notification tracking
~~~~~~~~~~~~~~~~~~~~~

A process application consumes events by reading event notifications from its notification
log readers. The events are retrieved in a reliable order, without race conditions or
duplicates or missing items.

To keep track of its position in the notification log, a process application will create
a new tracking record for each event notification it processes. The tracking records
determine how far the process has progressed through the notification log. Tracking
records are used to set the position of the notification log reader when the process
is commenced or resumed.


Policies
~~~~~~~~

A process application will respond to events according to its policy. Its policy might
do nothing in response to one type of event, and it might call an aggregate method in
response to another type of event. The aggregate method may trigger new domain events.

There can only be one tracking record for each notification. So once the tracking record
has been written it can't be written again, and neither can any new events unfortunately
triggered by duplicate calls to aggregate commands (which may even succeed and which may
not be idempotent). If an event can be processed at all, then it will be processed exactly
once.

However the policy responds to an event, the process application will write one tracking
record, along with any new event records, in an atomic database transaction.


Atomicity
~~~~~~~~~

A process application is as reliable as the atomicity of its database transactions,
just like a ratchet is as strong as its teeth and pawl. The atomicity of the
database transactions guarantees separately the reliability of both the notification
log being consumed (teeth) and the notification tracking records (pawl).

If some of the new records can't be written, then none are. If anything goes wrong
before all the records have been written, the transaction will abort, and none of
the records will be written. On the other hand, if a tracking record has been written,
then so will any new event records, and the process will have fully completed an atomic
progression.

The atomicity of the recording and consumption determines the production as atomic:
a continuous stream of events is processed in discrete, indivisible units. Hence,
interruptions can only cause delays. It is assumed that whatever records have been
committed by a process will not somehow be damaged by a sudden termination of the
process.


System of processes
-------------------

The library's class ``System`` can be used to
define a system of process applications independently of how it may be run.

In a system, one process application can follow another. One process can
follow two other processes in a slightly more complicated system. A system
could be just one process following itself.


Scale-independence
~~~~~~~~~~~~~~~~~~

The system can be run at different scales, but the definition of the system is
independent of scale.

A system of process applications can be run in a single thread, with synchronous propagation
and processing of events. This is intended as a development mode.

A system can also be run with multiple operating system processes, with asynchronous
propagation and processing of events. This is "diachronic" parallelism, like the way
a pipelined CPU core has stages. Having an asynchronous pipeline means events at
different stages can be processed at the same time. This kind of parallelism can
improve throughput, but perhaps its greatest benefit is the reliable foundation for
writing a "saga" or a "process managers", for accomplishing a complicated sequence
involving different aggregates and perhaps different bounded contexts without
long-lived transactions.

Just like a CPU can have many pipelines (cores) running different programs in parallel, a
system of process applications can have many parallel pipelines. Having many pipelines
means that many events can be processed at the same stage at the same time. This kind of
"synchronic" parallelism allows the system to take advantage of the scale of its infrastructure.

It is possible to run such a system with one operating system process dedicated to each
application process for each pipeline (see below). It would be possible to have a pool of
workers operating on a single of queue prompts, switching application and partition according
to the prompt (not yet implemented).


Causal dependencies
~~~~~~~~~~~~~~~~~~~

If an aggregate is created and then updated, the second event is causally dependent on
the first. Causal dependencies between events are detected and used to synchronise
the processing of parallel pipelines downstream. Downstream processing of one pipeline
can wait for an event to be processed in another. The causal dependencies are automatically
inferred by detecting the originator ID and version of aggregates as they are retrieved.
The old notification is referenced in the new notification. Downstream can then check all causal
dependencies have been processed, using its tracking records. (As optimisation, in case there
are many dependencies in the same pipeline, only the newest dependency in each pipeline is
included. By default in the library, only dependencies in different pipelines are included.
If dependencies from all pipelines were included, each pipeline could be processed in parallel.)


Kahn process networks
~~~~~~~~~~~~~~~~~~~~~

Because a notification log functions effectively as a FIFO, a system of
determinate process applications can be recognised as a `Kahn Process Network
<https://en.wikipedia.org/wiki/Kahn_process_networks>`__ (KPN).

Kahn Process Networks are determinate systems. If a system of process applications
happens to involve processes that are not determinate, or if the processes split and
combine or feedback in a random way so that nondeterminacy is introduced by design,
the system as a whole will not be determinate, and could be described in more general
terms as "dataflow" or "stream processing".

Whether or not a system of process applications is determinate, the processing will
be reliable.

.. If persistence were optional, this design could be used for high-performance applications
.. which would be understood to be less durable. Data could be streamed out asynchronously
.. and still stored atomically but after the processing notifications are available.
.. Resuming could then go back several steps, and perhaps a signal could be sent so
.. downstream restarts from an earlier step. Or maybe the new repeat processing could
.. be ignored by downstream, having already processed those items.


.. Refactoring
.. ~~~~~~~~~~~

.. Todo: Something about moving from a single process application to two. Migrate
.. aggregates by replicating those events from the notification log, and just carry
.. on.


Example
=======

The example below is suggestive of an orders-reservations-payments system.
The system automatically processes new orders by making a reservation, and
then a payment; facts that are registered with the order, as they happen.

The behaviour of the system is entirely defined by the combination of the
aggregates and the process policies, and the sequence defined in the system.

The "orders, reservations, payments" system is run: firstly
as a single threaded system; then with multiprocessing using a single pipeline;
and finally with both multiprocessing and multiple pipelines.

Aggregates
----------

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

        class Reserved(Event):
            def mutate(self, order):
                order.is_reserved = True
                order.reservation_id = self.reservation_id

        class Paid(Event):
            def mutate(self, order):
                order.is_paid = True
                order.payment_id = self.payment_id

        def set_is_reserved(self, reservation_id):
            assert not self.is_reserved, "Order {} already reserved.".format(self.id)
            self.__trigger_event__(Order.Reserved, reservation_id=reservation_id)

        def set_is_paid(self, payment_id):
            assert not self.is_paid, "Order {} already paid.".format(self.id)
            self.__trigger_event__(self.Paid, payment_id=payment_id)


A ``Reservation`` can be created. A reservation has an ``order_id``.

.. code:: python

    class Reservation(AggregateRoot):
        def __init__(self, order_id, **kwargs):
            super(Reservation, self).__init__(**kwargs)
            self.order_id = order_id

        class Created(AggregateRoot.Created):
            pass

        @classmethod
        def create(cls, order_id):
            return cls.__create__(order_id=order_id)


A ``Payment`` can be made. A payment also has an ``order_id``.

.. code:: python

    class Payment(AggregateRoot):
        def __init__(self, order_id, **kwargs):
            super(Payment, self).__init__(**kwargs)
            self.order_id = order_id

        class Created(AggregateRoot.Created):
            pass

        @classmethod
        def create(self, order_id):
            return self.__create__(order_id=order_id)

Factory
-------

The orders factory ``create_new_order()`` is decorated with the ``@retry`` decorator,
to be resilient against both concurrency conflicts and any operational errors.

.. code:: python

    from eventsourcing.domain.model.decorators import retry
    from eventsourcing.exceptions import OperationalError, RecordConflictError

    @retry((OperationalError, RecordConflictError), max_attempts=10, wait=0.01)
    def create_new_order():
        order = Order.__create__()
        order.__save__()
        return order.id

.. Todo: Raise and catch ConcurrencyError instead of RecordConflictError (convert somewhere
.. or just raise ConcurrencyError when there is a record conflict?).

As shown in previous sections, the behaviours of this domain model can be fully tested
with simple test cases, without involving any other components.


Processes
---------

A process application has a policy. The policy may respond to a domain
events by executing a command on an aggregate.

In the code below, the Reservations process policy responds to new orders by creating a
reservation. The Orders process responds to new reservations by setting an order
as reserved.

The Payments process responds when as order is reserved by making a payment. The
Orders process responds to new payments, by setting an order as paid.

.. code:: python

    from eventsourcing.application.process import Process


    class Orders(Process):
        persist_event_type=Order.Event

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

The ``Orders`` process will persist events of type ``Order.Event``, so that
orders can be created directly using the factory ``create_new_order()``.

When called, a process policy is given a ``repository`` and an ``event``. In process
policies, always use the given repository to access existing aggregates, so that
changes and causal dependencies can be automatically detected by the process application.
In other words, don't use ``self.repository``. The ``Process`` gives the policy a wrapped
version of its repository, so it can detect which aggregates were used, and which were changed.

.. code:: python

    class Reservations(Process):
        def policy(self, repository, event):
            if isinstance(event, Order.Created):
                # Create a reservation.
                return Reservation.create(order_id=event.originator_id)


Policies should normally return new aggregates to the caller, but do not need to return
existing aggregates that have been accessed or changed.

.. code:: python

    class Payments(Process):
        def policy(self, repository, event):
            if isinstance(event, Order.Reserved):
                # Create a payment.
                return Payment.create(order_id=event.originator_id)


Please note, the ``__save__()`` method of aggregates should never be called in a process policy,
because pending events from both new and changed aggregates will be automatically collected by
the process application after its ``policy()`` method has returned. To be reliable, a process
application needs to commit all the event records atomically with a tracking record, and calling
``__save__()`` will instead commit new events in a separate transaction.


Tests
-----

Process policies are easy to test.

In the orders policy test below, an existing order is marked as reserved because
a reservation was created.

.. code:: python

    from uuid import uuid4

    def test_orders_policy():

        # Prepare fake repository with a real Order aggregate.
        fake_repository = {}

        order = Order.__create__()
        fake_repository[order.id] = order

        # Check order is not reserved.
        assert not order.is_reserved

        # Process reservation created.
        with Orders() as process:

            event = Reservation.Created(originator_id=uuid4(), originator_topic='', order_id=order.id)
            process.policy(repository=fake_repository, event=event)

        # Check order is reserved.
        assert order.is_reserved


    # Run the test.
    test_orders_policy()

In the payments policy test below, a new payment is created because an order was reserved.

.. code:: python

    def test_payments_policy():

        # Prepare fake repository with a real Order aggregate.
        fake_repository = {}

        order = Order.__create__()
        fake_repository[order.id] = order

        # Check policy creates payment whenever order is reserved.
        event = Order.Reserved(originator_id=order.id, originator_version=1)

        with Payments() as process:
            payment = process.policy(repository=fake_repository, event=event)
            assert isinstance(payment, Payment), payment
            assert payment.order_id == order.id


    # Run the test.
    test_payments_policy()

It isn't necessary to return changed aggregates for testing purposes. The test
will already have a reference to the aggregate, since it will have constructed
the aggregate before passing it to the policy, so the test will already be in a
good position to check that already existing aggregates are changed by the policy
as expected. The test gives a ``fake_repository`` to the policy, which contains
the ``order`` aggregate expected by the policy.

.. To explain a little bit, in normal use, when new events are retrieved
.. from an upstream notification log, the ``policy()`` method is called by the
.. ``call_policy()`` method of the ``Process`` class. The ``call_policy()`` method wraps
.. the process application's aggregate repository with a wrapper that detects which
.. aggregates are used by the policy, and calls the ``policy()`` method with the events
.. and the wrapped repository. New aggregates returned by the policy are appended
.. to this list. New events are collected from this list of aggregates by getting
.. any (and all) pending events. The records are then committed atomically with the
.. tracking record. Calling ``__save__()`` will avoid the new events being included
.. in this mechanism and will spoil the reliability of the process. As a rule, don't
.. ever call the ``__save__()`` method of new or changed aggregates in a process
.. application policy. And always use the given ``repository`` to retrieve aggregates,
.. rather than the original process application's repository (``self.repository``)
.. which doesn't detect which aggregates were used when your policy was called.

System
------

A system can be defined as a network of processes that follow each other.

In this example, the orders and the reservations processes follow
each other. Also the payments and the orders processes follow each
other. There is no direct relationship between reservations and payments.

.. code:: python

    from eventsourcing.application.process import System


    system = System(
        Orders | Reservations | Orders,
        Orders | Payments | Orders
    )

The library's ``System`` class is constructed with pipelines of
process classes. For example, ``A | B | C`` would have ``C``
following ``B`` and ``B`` following ``A``.  The pipeline ``A | A``
has that ``A`` following ``A``. The pipelines ``A | B | A, A | C | A`` is equivalent
to the pipeline ``A | B | A | C | A``.

Although a process class can appear many times, there will only be one
instance of each process in the system. Each process may follow more
than one process. This can be recognised as the "pipes and filters"
pattern, where the applications function effectively as filters.

Please note, aggregates are segregated within an application. Each
application can only access the aggregates it has created. In this example,
an order aggregate created by the orders process is neither available in the
repositories of the reservations nor the payments applications.
This can be recognised as the "bounded context" pattern.

State is only propagated between applications in a system through
notification logs only. If one application could use the aggregates
of another application, processing could produce different results
at different times, and in consequence the process wouldn't be reliable.
If necessary, an application can always replicate the state of an
aggregate within its own context in an application it is following,
by projecting its events as they are read from the notification log.

In this example, the Orders process, specifically the Order aggregate
combined with the Orders process policy, could function effectively as a
"saga", or "process manager", or "workflow manager", in that it can effectively
control a sequence of steps involving other bounded contexts and other
aggregates, steps that might otherwise be controlled with a "long-lived
transaction", with errors handled as part of the logic of the application.

.. Except for the definition and implementation of process,
.. there are no special concepts or components. There are only policies and
.. aggregates and events, and the way they are processed in a process application.
.. There isn't a special mechanism that provides reliability despite the rest
.. of the system, each aggregate is equally capable of functioning as a saga object,
.. every policy is capable of functioning as a process manager or workflow.
.. There doesn't need to be a special mechanism for coding compensating
.. transactions. If required, a failure (e.g. to create a payment) can be
.. coded as an event that can processed to reverse previous steps (e.g.
.. to cancel a reservation).


Single threaded
~~~~~~~~~~~~~~~

If the ``system`` object is used as a context manager, the process
applications will be setup to work in a single thread in the current
process. Events will be processed with synchronous handling of prompts,
so that policies effectively call each other recursively. This avoids
concurrency and is useful when developing and testing a system of process
applications, because it runs quickly and the behaviour is easy to follow.

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


Multiprocessing
~~~~~~~~~~~~~~~

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

.. (For those concerned about having too much data in the relational database, it
.. would be possible to expand capacity by: replicating events from the relational
.. database to a more scalable distributed database; changing the event store to
.. read older events from the distributed database if the relational database doesn't
.. have those events, and then removing older events and older snapshots from the
.. relational database. Snapshotting could be configured to avoid getting
.. events from the distributed database for normal operations. The relational database
.. could than have a relatively constant  volume of data. Following the analogy
.. with CPUs, the relational database might correspond to the L2 cache, and the
.. distributed database might correspond to the L3 cache. Please note, this idea
.. isn't currently implemented in the library.)

In this example, the process applications use a MySQL database.

.. code:: python

    import os

    host = os.getenv('MYSQL_HOST', '127.0.0.1')
    user = os.getenv('MYSQL_USER', 'root')
    password = os.getenv('MYSQL_PASSWORD', '')
    os.environ['DB_URI'] = 'mysql+pymysql://{}:{}@{}/eventsourcing'.format(user, password, host)


Single pipeline
~~~~~~~~~~~~~~~

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


.. Todo: Command logging process application, that is presented
.. as being suitable for use in both a multi-threaded Web
.. application server, and a worker queue processing stuff, the
.. worker or the Web application instance could have their commands
.. distributed across pipelines in a system at random. The command
.. logging process could do that. A command could be the name of a
.. method on the process application object, and it could have args
.. used to call the method. An actor could be used to send a message,
.. and the actor ID could be included in the command, so that when
.. a response is created (how?), the request actor could be sent
.. a message, so clients get a blocking call that doesn't involve polling.

The MySQL database tables were created by the code above, because the ``Orders`` process
was constructed with ``setup_tables=True``, which is by default ``False`` in the ``Process``
class.

The code below uses the library's ``Multiprocess`` class to run the ``system``.
By default, it starts one operating system process for each process application
in the system, which in this example will give three child operating system processes.

.. code:: python

    from eventsourcing.application.multiprocess import Multiprocess

The operating system processes can be started by using the ``multiprocess``
object as a context manager, which calls ``start()`` on entry and ``close()``
on exit.

The process applications read their upstream notification logs when they start,
so the unprocessed ``Order.Created`` event is picked up and processed immediately.
Wait for the results by polling the aggregate state.

.. code:: python

    import time

    if __name__ == '__main__':

        with Orders() as app, Multiprocess(system):

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

Multiple pipelines
~~~~~~~~~~~~~~~~~~

The system can be run with many pipelines. With many pipelines, many events can
be processed at the same time by each process in the system.

In the example below, there are five pipelines and three process applications, which
gives fifteen child operating system processes. All fifteen operating system processes
will share the same database. It would be possible to run the system with e.g. pipelines
0-7 on one machine, pipelines 8-15 on another machine, and so on.

.. code:: python

    from eventsourcing.utils.uuids import uuid_from_pipeline_name

    num_pipelines = 5

    pipeline_ids = [uuid_from_pipeline_name(i) for i in range(num_pipelines)]


Below, twenty-five orders are created in each of the five pipelines, giving one hundred and
twenty-five orders in total. Please note, when creating the new aggregates, the Orders
process application needs to be told which pipeline to use.

.. Todo: Replace with command process?

.. code:: python

    if __name__ == '__main__':

        with Orders() as app, Multiprocess(system, pipeline_ids=pipeline_ids):

            # Create new orders.
            order_ids = []
            num_orders_per_pipeline = 25

            for _ in range(num_orders_per_pipeline):
                for pipeline_id in pipeline_ids:
                    app.change_pipeline(pipeline_id)

                    order_id = create_new_order()
                    order_ids.append(order_id)


            # Wait for orders to be reserved and paid.
            retries = 10 + 10 * num_orders_per_pipeline * len(pipeline_ids)
            for i, order_id in enumerate(order_ids):

                while not app.repository[order_id].is_reserved:
                    time.sleep(0.1)
                    retries -= 1
                    assert retries, "Failed set order.is_reserved {} ({})".format(order_id, i)

                while retries and not app.repository[order_id].is_paid:
                    time.sleep(0.1)
                    retries -= 1
                    assert retries, "Failed set order.is_paid ({})".format(i)

..            # Calculate timings from event timestamps.
..            orders = [app.repository[oid] for oid in order_ids]
..            min_created_on = min([o.__created_on__ for o in orders])
..            max_created_on = max([o.__created_on__ for o in orders])
..            max_last_modified = max([o.__last_modified__ for o in orders])
..            create_duration = max_created_on - min_created_on
..            duration = max_last_modified - min_created_on
..            rate = len(order_ids) / float(duration)
..            period = 1 / rate
..            print("Orders created rate: {:.1f} order/s".format((len(order_ids) - 1) / create_duration))
..            print("Orders processed: {} orders in {:.3f}s at rate of {:.1f} "
..                  "orders/s, {:.3f}s each".format((len(order_ids) - 1), duration, rate, period))
..
..            # Print min, average, max duration.
..            durations = [o.__last_modified__ - o.__created_on__ for o in orders]
..            print("Min order processing time: {:.3f}s".format(min(durations)))
..            print("Mean order processing time: {:.3f}s".format(sum(durations) / len(durations)))
..            print("Max order processing time: {:.3f}s".format(max(durations)))



.. Since the above policy ``sleep(0.5)`` statements ensure each order takes at least one second
.. to process, so varying the number of pipelines and the number of orders demonstrates
.. even on a machine with few cores (e.g. my laptop) that processing is truly
.. concurrent both across the process applications and across the pipelines of the
.. system. (The total processing time for a batch of orders tends towards the duration
.. of the longest step, multiplied by the size of the batch, divided by the number of
.. pipelines. So the maximum rate of a system is the number of pipelines divided by
.. the duration of the longest step. Obviously, the minimum processing time for a single
.. order, its total latecy, is equal to the sum of the durations of each step regardless
.. of the batch size or the number of pipelines.)

.. Without the ``sleep(0.5)`` statements, the system with its five-step process can process
.. on my small laptop about twenty-five orders per second per pipeline, approximately 40ms
.. for each order, with min and average order processing times of approximately 100ms and
.. 150ms for the five steps. The atomic database transaction code takes about 4ms from opening
.. the transaction in Python to closing the session in Python. So it seems there is room for
.. improving performance in future versions of the library.

.. Most business applications process less than one command per second. However, to process spikes
.. in the demand without spikes in latency, or if continuous usage gives ten or a hundred
.. times more commands per second, then the number of pipelines could be increased accordingly.
.. On "Amazon Prime Day" in 2016, Amazon Inc. sold an estimated 636 items per second.
.. Eventually with this design, the database would limit throughput. But since the operations
.. are pipelined, the database could be scaled vertically (more cores and memory) in proportion
.. to the number of pipelines.

The work of increasing the number of pipelines, and starting new operating system
processes, could be automated. Also, the cluster scaling could be automated, and
processes distributed automatically across the cluster. Actor model seems like a
good foundation for such automation.



.. Todo: Make option to send event as prompt. Change Process to use event passed as prompt.

.. There are other ways in which the reliability could be relaxed. Persistence could be
.. optional. ...

Actor model
~~~~~~~~~~~

An Actor model library, such as `Thespian Actor Library
<https://github.com/kquick/Thespian>`__, could be used to run
a pipelined system of process applications as actors.

A system actor could start an actor for each pipeline-stage
when its address is requested, or otherwise make sure there is
one running actor for each process application-pipeline.

Actor processes could be automatically distributed across a cluster. The
cluster could auto-scale according to CPU usage (or perhaps network usage).
New nodes could run a container that begins by registering with the actor
system, (unless there isn't one, when it begins an election to become leader?)
and the actor system could run actors on it, reducing the load on other nodes.

Prompts from one process application-pipeline could be sent to another
as actor messages, rather than with a publish-subscribe service. The address
could be requested from the system, and the prompt sent directly.

To aid development and testing, actors could run without any
parallelism, for example with the "simpleSystemBase" actor
system in Thespian.

Partitioning of the system could be automated with actors. A system actor
(started how? leader election? Kubernetes configuration?) could increase or
decrease the number of system pipelines, according to the rate at which events
are being added to the system command process, compared to the known (or measured)
rate at which commands can be processed by the system. If there are too many actors
dying from lack of work, then to reduce latency of starting an actor for each event
(extreme case), the number of pipelines could be reduced, so that there are enough
events to keep actors alive. If there are fewer pipelines than nodes, then some nodes
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
applications-pipelines go well together. The process appliation-actor idea seems like a
much better idea that the aggregate-actor idea. Perhaps aggregates could also usefully be actors,
but an adapter would need to be coded to process messages as commands, to return pending events as
messages, and so on, to represent themselves as message, and so on. It can help to have many
threads running consecutively through an aggregate, especially readers. The consistency of the
aggregate state is protected with optimistic concurrency control. Wrapping an aggregate as
an actor won't speed things up, unless the actor is persistent, which uses resources. Aggregates
could be cached inside the process application-pipeline, especially if it is know that they will
probably be reused.

.. Todo: Method to fastforward an aggregate, by querying for and applying new events?

(Running a system of process applications with actors is not yet implemented in the library.)


.. Todo: Actor model deployment of system.




Pool of workers
~~~~~~~~~~~~~~~

An alternative to having a thread dedicated to every process application for each pipeline,
the prompts could be sent to via a queue to a pool of workers, which change pipeline and
application according to the prompt. Causal dependencies would be needed for all notifications,
which is not the library default. The library does not currently support processing events with
a pool of workers.


Integration with APIs
=====================

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
