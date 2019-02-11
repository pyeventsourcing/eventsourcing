==================
Process and system
==================

This section is about process applications. A process application is
a projection into an event sourced application. A system of process
applications can be constructed by linking applications together in
a pipeline.

Reliability is the most important concern in this section. A process
is considered to be reliable if its product is entirely unaffected
(except in being delayed) by a sudden termination of the process
happening at any time. The only trick is remembering that, in general,
production is determined by consumption with recording. In particular,
if the consumption and the recording are reliable, then the product of
the process is bound to be reliable.

This definition of the reliability of a process doesn't include availability.
Infrastructure unreliability may cause processing delays. Disorderly
environments shouldn't cause disorderly processing. The other important
concerns discussed in this section are scalability and maintainability.


.. (If we can reject the pervasive description of `distributed systems
.. <https://en.wikipedia.org/wiki/Distributed_computing>`__ as a system of
.. passing messages, where `message passing means sending messages
.. <https://en.wikipedia.org/wiki/Message_passing>`__, then we do not need
.. to be concerned with the number of times a message is delivered, and can
.. avoid failing to find a good solution to the false problem of guaranteeing
.. once-only delivery of messages, which in itself doesn't determine the
.. processing as reliable. Hence we do not need to protect against "at least
.. once" delivery. We can avoid the restriction of making aggregate commands
.. idempotent. We can also avoid storing all the received messages in order to
.. de-duplicate and reorder.)

.. To limit this discussion even further, any programming errors in the policies or
.. aggregates of a process that may inadvertently define pathological behaviour are
.. considered to be a separate concern.

.. contents:: :local:


Please note, the code presented in the example below works only with the library's
SQLAlchemy record manager. Django support is planned, but not yet implemented. Support
for Cassandra is being considered but applications will probably be simple replications
of application state, due to the limited atomicity of Cassandra's lightweight transactions.
Cassandra could be used to archive events written firstly into a relational database.
Events could be removed from the relational database before storage limits are encountered.
Events missing in the relational database could be sourced from Cassandra.


Overview
========

Process application
-------------------

The library's process application class ``Process`` functions as a projection into
an event-sourced application. Applications and projections are discussed in previous
sections. The ``Process`` class extends ``SimpleApplication`` by also reading notification
logs and writing tracking records. A process application also has a policy that defines how
it will respond to domain events it reads from notification logs.


Notification tracking
~~~~~~~~~~~~~~~~~~~~~

A process application consumes events by reading domain event notifications
from its notification log readers. The events are retrieved in a reliable order,
without race conditions or duplicates or missing items. Each notification in a
notification log has a unique integer ID, and the notification log IDs form a
contiguous sequence.

To keep track of its position in the notification log, a process application
will create a new tracking record for each event notification it processes.
The tracking records determine how far the process has progressed through
the notification log. The tracking records are used to set the position
of the notification log reader when the process is commenced or resumed.


Policies
~~~~~~~~

A process application will respond to events according to its policy. Its policy might
do nothing in response to one type of event, and it might call an aggregate command method
in response to another type of event. If the aggregate method triggers new domain events,
they will be available in its notification log for others to read.

There can only be one tracking record for each notification. Once the tracking record
has been written it can't be written again, and neither can any new events unfortunately
triggered by duplicate calls to aggregate commands (which may not be idempotent). If an
event can be processed at all, then it will be processed exactly once.

Whatever the policy response, the process application will write one tracking
record for each notification, along with new stored event and notification records,
in an atomic database transaction.


Atomicity
~~~~~~~~~

A process application is as reliable as the atomicity of its database transactions,
just like a ratchet is as strong as its teeth (notification log) and pawl (tracking
records).

If some of the new records can't be written, then none are. If anything goes wrong
before all the records have been written, the transaction will abort, and none of
the records will be written. On the other hand, if a tracking record is written,
then so are any new event records, and the process will have fully completed an atomic
progression.

The atomicity of the recording and consumption determines the production as atomic:
a continuous stream of events is processed in discrete, sequenced, indivisible units.
Hence, interruptions can only cause delays.

.. It is assumed that whatever records have been
.. committed by a process will not somehow be damaged by a sudden termination of the
.. process.


System of processes
-------------------

The library class ``System`` can be used to define a system of process applications,
independently of scale.

In a system, one process application can follow another. One process can
follow two other processes in a slightly more complicated system. A system
could be just one process following itself.


Scale-independence
~~~~~~~~~~~~~~~~~~

The system can run at different scales, but the definition of the system is
independent of scale.

A system of process applications can run in a single thread, with synchronous propagation
and processing of events. This is intended as a development mode.

A system can also run with multiple operating system processes, with asynchronous
propagation and processing of events. Having an asynchronous pipeline means events at
different stages can be processed at the same time. This could be described as "diachronic"
parallelism, like the way a pipelined CPU core has stages. This kind of parallelism can
improve throughput, up to a limit provided by the number of steps required by the domain.
The reliability of the sequantial processing allows one to write a reliable "saga" or a
"process manager". In other words, a complicated sequence involving different aggregates,
and perhaps different bounded contexts, can be implemented reliably without long-lived
transactions.

To scale the system further, a system of process applications can run with parallel instances
of the pipeline expressions, just like the way an operating system can use many cores (pipelines)
processing instruction in parallel. Having parallel pipelines means that many events can be
processed at the same stage at the same time. This "synchronic" parallelism allows a system
to take advantage of the scale of its infrastructure.


Causal dependencies
~~~~~~~~~~~~~~~~~~~

If an aggregate is created and then updated, the second event is causally dependent on
the first. Causal dependencies between events can be detected and used to synchronise
the processing of parallel pipelines downstream. Downstream processing of one pipeline
can wait for an event to be processed in another.

In the process applications, the causal dependencies are automatically inferred by detecting
the originator ID and version of aggregates as they are retrieved. The old notifications are
referenced in the first new notification. Downstream can then check all causal dependencies have
been processed, using its tracking records.

In case there are many dependencies in the same pipeline, only the newest dependency in each
pipeline is included. By default in the library, only dependencies in different pipelines are
included. If causal dependencies from all pipelines were included in each notification, each
pipeline could be processed in parallel, to an extent limited by the dependencies between the
notifications.


Kahn process networks
~~~~~~~~~~~~~~~~~~~~~

Because a notification log and reader functions effectively as a FIFO, a system of
determinate process applications can be recognised as a `Kahn Process Network
<https://en.wikipedia.org/wiki/Kahn_process_networks>`__ (KPN).

Kahn Process Networks are determinate systems. If a system of process applications
happens to involve processes that are not determinate, or if the processes split and
combine or feedback in a random way so that nondeterminacy is introduced by design,
the system as a whole will not be determinate, and could be described in more general
terms as "dataflow" or "stream processing".

Whether or not a system of process applications is determinate, the processing will
be reliable (results unaffected by infrastructure failures).

High performance or "real time" processing could be obtained by avoiding writing to a
durable database and instead running applications with an in-memory database.


Process manager
~~~~~~~~~~~~~~~

A process application, specifically an aggregate combined with a policy in a process application,
could function effectively as a "saga", or "process manager", or "workflow manager". That is, it
could effectively control a sequence of steps involving other aggregates in other bounded contexts,
steps that might otherwise be controlled with a "long-lived transaction". It could 'maintain
the state of the sequence and determine the next processing step based on intermediate results'
(quote from Enterprise Integration Patterns). Exceptional "unhappy path" behaviour can be
implemented as part of the logic of the application.

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
The system automatically processes a new Order by making a Reservation, and
then a Payment; facts registered with the Order as they happen.

The behaviour of the system is entirely defined by the combination of the
aggregates and the policies of its process applications. This allows highly
maintainable code, code that is easily tested, easily understood, easily changed.

Below, the "orders, reservations, payments" system is run: firstly as a single
threaded system; then with multiprocessing using a single pipeline; and finally
with both multiprocessing and multiple pipelines.


Aggregates
----------

In the code below, event-sourced aggregates are defined for orders, reservations,
and payments. The ``Order`` class is for "orders". The ``Reservation`` class is
for "reservations". And the ``Payment`` class is for "payments".

In the model below, an order can be created. A new order
can be set as reserved, which involves a reservation
ID. Having been created and reserved, an order can be
set as paid, which involves a payment ID.

.. code:: python

    from eventsourcing.domain.model.aggregate import AggregateRoot


    class Order(AggregateRoot):
        def __init__(self, command_id=None, **kwargs):
            super(Order, self).__init__(**kwargs)
            self.command_id = command_id
            self.is_reserved = False
            self.is_paid = False

        class Event(AggregateRoot.Event):
            pass

        class Created(Event, AggregateRoot.Created):
            def __init__(self, **kwargs):
                assert 'command_id' in kwargs, kwargs
                super(Order.Created, self).__init__(**kwargs)

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
            self.__trigger_event__(
                Order.Reserved, reservation_id=reservation_id
            )

        def set_is_paid(self, payment_id):
            assert not self.is_paid, "Order {} already paid.".format(self.id)
            self.__trigger_event__(
                self.Paid, payment_id=payment_id, command_id=self.command_id
            )


A reservation can also be created. A reservation has an ``order_id``.

.. code:: python

    class Reservation(AggregateRoot):
        def __init__(self, order_id, **kwargs):
            super(Reservation, self).__init__(**kwargs)
            self.order_id = order_id

        class Created(AggregateRoot.Created):
            pass


Similarly, a payment can be created. A payment also has an ``order_id``.

.. code:: python

    class Payment(AggregateRoot):
        def __init__(self, order_id, **kwargs):
            super(Payment, self).__init__(**kwargs)
            self.order_id = order_id

        class Created(AggregateRoot.Created):
            pass


.. Factory
.. -------
..
.. The orders factory ``create_new_order()`` is decorated with the ``@retry`` decorator,
.. to be resilient against both concurrency conflicts and any operational errors.
..
.. .. code:: python
..
..     from eventsourcing.domain.model.decorators import retry
..     from eventsourcing.exceptions import OperationalError, RecordConflictError
..
..     @retry((OperationalError, RecordConflictError), max_attempts=10, wait=0.01)
..     def create_new_order():
..         order = Order.__create__()
..         order.__save__()
..         return order.id

.. Todo: Raise and catch ConcurrencyError instead of RecordConflictError (convert somewhere
.. or just raise ConcurrencyError when there is a record conflict?).

As shown in previous sections, the behaviours of this domain model can be fully tested
with simple test cases, without involving any other components.


Commands
--------

Commands have been discussed so far as methods on aggregate objects. Here, system
commands are introduced, as event sourced aggregates. System command aggregates can
be created, and set as "done". A commands process application can be followed by other
applications. This provides a standard interface for system input.

In the code below, the system command class ``CreateNewOrder`` is defined using the
library ``Command`` class. The ``Command`` class extends the ``AggregateRoot`` class
with a method ``done()`` and a property ``is_done``.

The ``CreateNewOrder`` class extends the library's ``Command`` class with an event
sourced ``order_id`` attribute, which will be used to associate the command's objects
with the orders created by the system in response.

.. code:: python

    from eventsourcing.domain.model.command import Command
    from eventsourcing.domain.model.decorators import attribute


    class CreateNewOrder(Command):
        @attribute
        def order_id(self):
            pass


A ``CreateNewOrder`` command can be assigned an order ID. Its ``order_id`` is initially ``None``.

The behaviour of a system command aggregate can be fully tested with simple test cases,
without involving any other components.

.. code:: python

    from uuid import uuid4

    def test_create_new_order_command():
        # Create a "create new order" command.
        cmd = CreateNewOrder.__create__()

        # Check the initial values.
        assert cmd.order_id is None
        assert cmd.is_done is False

        # Assign an order ID.
        order_id = uuid4()
        cmd.order_id = order_id
        assert cmd.order_id == order_id

        # Mark the command as "done".
        cmd.done()
        assert cmd.is_done is True

        # Check the events.
        events = cmd.__batch_pending_events__()
        assert len(events) == 3
        assert isinstance(events[0], CreateNewOrder.Created)
        assert isinstance(events[1], CreateNewOrder.AttributeChanged)
        assert isinstance(events[2], CreateNewOrder.Done)


    # Run the test.
    test_create_new_order_command()

One advantage of having distinct commands is that a new version of the system can be
verified by checking the same commands generates the same state as the old version.


Processes
---------

A process application has a policy. The policy may respond to a domain
event by calling a command method on an aggregate.

The orders process responds to new commands by creating a new ``Order``. It responds
to new reservations by setting an ``Order`` as reserved. And it responds to a new ``Payment``,
by setting an ``Order`` as paid.

.. code:: python

    from eventsourcing.application.process import ProcessApplication
    from eventsourcing.utils.topic import resolve_topic


    class Orders(ProcessApplication):
        persist_event_type=Order.Event

        @staticmethod
        def policy(repository, event):
            if isinstance(event, CreateNewOrder.Created):
                command_class = resolve_topic(event.originator_topic)
                if command_class is CreateNewOrder:
                    return Order.__create__(command_id=event.originator_id)

            elif isinstance(event, Reservation.Created):
                # Set the order as reserved.
                order = repository[event.order_id]
                assert not order.is_reserved
                order.set_is_reserved(event.originator_id)

            elif isinstance(event, Payment.Created):
                # Set the order as paid.
                order = repository[event.order_id]
                assert not order.is_paid
                order.set_is_paid(event.originator_id)

The reservations process application responds to an ``Order.Created`` event
by creating a new ``Reservation`` aggregate.

.. code:: python

    class Reservations(ProcessApplication):
        @staticmethod
        def policy(repository, event):
            if isinstance(event, Order.Created):
                return Reservation.__create__(order_id=event.originator_id)


The payments process application responds to an ``Order.Reserved`` event
by creating a new ``Payment``.

.. code:: python

    class Payments(ProcessApplication):
        @staticmethod
        def policy(repository, event):
            if isinstance(event, Order.Reserved):
                return Payment.__create__(order_id=event.originator_id)

Additionally, the library class ``CommandProcess`` is extended by defining a policy that
responds to ``Order.Created`` events by setting the ``order_id`` on the command. It also
responds to ``Order.Paid`` events by setting the command as done.

.. code:: python

    from eventsourcing.application.command import CommandProcess
    from eventsourcing.domain.model.decorators import retry
    from eventsourcing.exceptions import OperationalError, RecordConflictError


    class Commands(CommandProcess):
        @staticmethod
        def policy(repository, event):
            if isinstance(event, Order.Created):
                cmd = repository[event.command_id]
                cmd.order_id = event.originator_id
            elif isinstance(event, Order.Paid):
                cmd = repository[event.command_id]
                cmd.done()

        @staticmethod
        @retry((OperationalError, RecordConflictError), max_attempts=10, wait=0.01)
        def create_new_order():
            cmd = CreateNewOrder.__create__()
            cmd.__save__()
            return cmd.id

The ``@retry`` decorator here protects against any contention writing to the ``Commands`` notification log.

Please note, the ``__save__()`` method of aggregates shouldn't be called in a process policy,
because pending events from both new and changed aggregates will be automatically collected by
the process application after its ``policy()`` method has returned. To be reliable, a process
application needs to commit all the event records atomically with a tracking record, and calling
``__save__()`` will instead commit events in a separate transaction. Policies should normally
return new aggregates to the caller, but do not need to return existing aggregates that have
been accessed or changed.


Tests
-----

Process policies are just functions, and are easy to test.

In the orders policy test below, an existing order is marked as reserved because
a reservation was created. The only complication comes from needing to prepare
at least a fake repository and a domain event, given as required arguments when
calling the policy in the test. If the policy response depends on already existing
aggregates, they will need to be added to the fake repository. A Python dict can
function effectively as a fake repository in such tests. It seems simplest to
directly use the model domain event classes and aggregate classes in these tests,
rather than coding `test doubles <https://martinfowler.com/bliki/TestDouble.html>`__.

.. code:: python

    from eventsourcing.application.sqlalchemy import SQLAlchemyApplication

    def test_orders_policy():
        # Prepare repository with a real Order aggregate.
        order = Order.__create__(command_id=None)
        repository = {order.id: order}

        # Check order is not reserved.
        assert not order.is_reserved

        # Process reservation created.
        with Orders.mixin(SQLAlchemyApplication)() as orders:
            event = Reservation.Created(originator_id=uuid4(), originator_topic='', order_id=order.id)
            orders.policy(repository=repository, event=event)

        # Check order is reserved.
        assert order.is_reserved


    # Run the test.
    test_orders_policy()

In the payments policy test below, a new payment is created because an order was reserved.

.. code:: python

    def test_payments_policy():

        # Prepare repository with a real Order aggregate.
        order = Order.__create__(command_id=None)
        repository = {order.id: order}

        # Check payment is created whenever order is reserved.
        with Payments.mixin(SQLAlchemyApplication)() as payments:
            event = Order.Reserved(originator_id=order.id, originator_version=1)
            payment = payments.policy(repository=repository, event=event)

        assert isinstance(payment, Payment), payment
        assert payment.order_id == order.id


    # Run the test.
    test_payments_policy()

It isn't necessary to return changed aggregates from the policy. The test
will already have a reference to the aggregate, since it will have constructed
the aggregate before passing it to the policy in the fake repository, so the test
will already be in a good position to check that already existing aggregates are
changed by the policy as expected. The test gives a ``repository`` to the policy,
which contains the ``order`` aggregate expected by the policy.

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

A system of process applications can be defined using one or many pipeline expressions.

The expression ``A | A`` would have a process application class called ``A`` following
itself. The expression ``A | B | C`` would have ``A`` followed by ``B`` and ``B``
followed by ``C``. This can perhaps be recognised as the "pipes and filters" pattern,
where the process applications function effectively as the filters.

In this example, firstly the ``Orders`` process will follow the ``Commands`` process
so that orders can be created. The ``Commands`` process will follow the ``Orders`` process,
so that commands can be marked as done when processing is complete.

.. code:: python

    commands_pipeline = Commands | Orders | Commands

Similarly, the ``Orders`` process and the ``Reservations`` process will follow
each other. Also the ``Orders`` and the ``Payments`` process will follow each other.

.. code:: python

    reservations_pipeline = Orders | Reservations | Orders
    payments_pipeline = Orders | Payments | Orders

The orders-reservations-payments system can be defined using these pipeline expressions.

.. code:: python

    from eventsourcing.application.system import System

    system = System(
        commands_pipeline,
        reservations_pipeline,
        payments_pipeline,
        infrastructure_class=SQLAlchemyApplication
    )

This is equivalent to a system defined with the following single pipeline expression.

.. code:: python

    system = System(
        Commands | Orders | Reservations | Orders | Payments | Orders | Commands,
        infrastructure_class=SQLAlchemyApplication
    )

Although a process application class can appear many times in the pipeline
expressions, there will only be one instance of each process when the pipeline
system is instantiated. Each application can follow one or many applications,
and can be followed by one or many applications.

State is propagated between process applications through notification logs only. This can
perhaps be recognised as the "bounded context" pattern. Each application can access only
the aggregates it has created. For example, an ``Order`` aggregate created by the ``Orders``
process is available in neither the repository of ``Reservations`` nor the repository of
``Payments``. That is because if an application could directly use the aggregates of another
application, processing could produce different results at different times, and in consequence
the processing wouldn't be reliable. If necessary, a process application could replicate the
state of an aggregate within its own context in an application it is following, by projecting
its events as they are read from an upstream notification log.

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
applications will run in a single thread in the current process.
Events will be processed with synchronous handling of prompts,
so that policies effectively call each other recursively.

In the code below, the ``system`` object is used as a context manager.
When used in this way, by default the process applications will share an
in-memory SQLite database.

.. code:: python

    system.setup_tables = True

    with system:
        # Create new order command.
        cmd_id = system.processes['commands'].create_new_order()

        # Check the command has an order ID and is done.
        cmd = system.processes['commands'].repository[cmd_id]
        assert cmd.order_id
        assert cmd.is_done

        # Check the order is reserved and paid.
        order = system.processes['orders'].repository[cmd.order_id]
        assert order.is_reserved
        assert order.is_paid

        # Check the reservation exists.
        reservation = system.processes['reservations'].repository[order.reservation_id]

        # Check the payment exists.
        payment = system.processes['payments'].repository[order.payment_id]

Basically, given the system is running, when a "create new order" command is
created, then the command is done, and an order has been both reserved and paid.

Everything happens synchronously, in a single thread, so that by the time
``create_new_order()`` has returned, the system has already processed the
command, which can be retrieved from the "commands" repository.

Running the system with a single thread and an in-memory database is
useful when developing and testing a system of process applications,
because it runs very quickly and the behaviour is very easy to follow.

.. The process applications above could run in different threads (not
.. yet implemented).


Multiprocessing
~~~~~~~~~~~~~~~

The example below shows the same system of process applications running in
different operating system processes, using the library's ``MultiprocessRunner`` class,
which uses Python's ``multiprocessing`` library.

Running the system with multiple operating system processes means the different processes
are running concurrently, so that as the payment is made for one order, another order might
get reserved, whilst a third order is at the same time created.

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

In this example, the process applications share a MySQL database.

.. code:: python

    import os

    os.environ['DB_URI'] = 'mysql+pymysql://{}:{}@{}/eventsourcing'.format(
        os.getenv('MYSQL_USER', 'root'),
        os.getenv('MYSQL_PASSWORD', ''),
        os.getenv('MYSQL_HOST', '127.0.0.1'),
    )

The process applications could each use their own separate database. If the
process applications were using different databases, upstream notification
logs would need to be presented in an API, so that downstream could read
notifications from a remote notification log, as discussed in the section
about notifications (using separate databases is not currently supported
by the ``MultiprocessRunner`` class).

The MySQL database needs to be created before running the next bit of code.

.. code::

    $ mysql -e "CREATE DATABASE eventsourcing;"

Before starting the system's operating system processes, let's create a ``CreateNewOrder``
command using the ``create_new_order()`` method on the ``Commands`` process (defined above).
Because the system isn't yet running, the command remains unprocessed.


.. code:: python


    with Commands.mixin(SQLAlchemyApplication)(setup_table=True) as commands:

        # Create a new command.
        cmd_id = commands.create_new_order()

        # Check command exists in repository.
        assert cmd_id in commands.repository

        # Check command is not done.
        assert not commands.repository[cmd_id].is_done

The database tables for storing events and tracking notification were created by the code
above, because the ``Commands`` process was constructed with ``setup_tables=True``, which
is by default ``False`` in the application classes.


Single pipeline
~~~~~~~~~~~~~~~

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

The code below uses the library's ``MultiprocessRunner`` class to run the ``system``.
It starts one operating system process for each process application
in the system, which in this example will give four child operating
system processes.

.. code:: python

    from eventsourcing.application.multiprocess import MultiprocessRunner

    multiprocessing_system = MultiprocessRunner(system, setup_tables=True)

The operating system processes can be started by using the ``multiprocess``
object as a context manager. The unprocessed commands will be processed
shortly after the various operating system processes have been started.

.. code:: python

    # Check the unprocessed command gets processed eventually.
    @retry((AssertionError, KeyError), max_attempts=100, wait=0.5)
    def assert_command_is_done(repository, cmd_id):
        assert repository[cmd_id].is_done

    # Process the command.
    with multiprocessing_system, Commands.mixin(SQLAlchemyApplication)() as commands:
        assert_command_is_done(commands.repository, cmd_id)

The process applications read their upstream notification logs when they start,
so the unprocessed command is picked up and processed immediately.


.. Each operating system processes runs a loop that begins by making a call to get prompts
.. pushed from upstream. Prompts are pushed downstream after events are recorded. The prompts
.. are responded to immediately by pulling and processing the new events. If the call to get
.. new prompts times out, then any new events in upstream notification logs are pulled anyway,
.. so that the notification log is effectively polled at a regular interval. The upstream log
.. is also pulled when the process starts. Hence if upstream suffers a sudden termination just
.. before the prompt is pushed, or downstream suffers a sudden termination just after receiving
.. the prompt, the processing will continue promptly and correctly after the process is restarted,
.. even though the prompt was lost. Please note, prompts merely reduce latency of polling, and
.. the system could function without them (just with more latency).


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

The system can run with multiple instances of the system's pipeline expressions. Running the
system with parallel pipelines means that each process application in the system
can process many events at the same time.

In the example below, there will be three parallel pipelines for the
system's four process applications, give twelve child operating system
processes altogether. Five orders will be processed in each pipeline,
so fifteen orders will processed by the system altogether.

.. code:: python

    num_pipelines = 3
    num_orders_per_pipeline = 5

Pipelines have integer IDs. In this example, the pipeline IDs are ``[0, 1, 2]``.

.. code:: python

    pipeline_ids = range(num_pipelines)

It would be possible to run the system with e.g. pipelines 0-7 on one machine, pipelines 8-15
on another machine, and so on.

The ``pipeline_ids`` are given to the ``MultiprocessRunner`` object.

.. code:: python

    multiprocessing_system = MultiprocessRunner(system, pipeline_ids=pipeline_ids)

With the multiprocessing system running each of the process applications
as a separate operating system process, and the commands process running
in the current process, commands are created in each pipeline of the commands
process, which causes orders to be processed by the system.

.. code:: python

    with multiprocessing_system, Commands.mixin(SQLAlchemyApplication)() as commands:

        # Create new orders.
        command_ids = []
        for _ in range(num_orders_per_pipeline):
            for pipeline_id in pipeline_ids:

                # Change the pipeline for the command.
                commands.change_pipeline(pipeline_id)

                # Create a "create new order" command.
                cmd_id = commands.create_new_order()
                command_ids.append(cmd_id)

        # Check all commands are eventually done.
        for i, command_id in enumerate(command_ids):
            assert_command_is_done(commands.repository, command_id)


..            # Calculate timings from event timestamps.
..            orders = [app.repository[oid] for oid in command_ids]
..            min_created_on = min([o.__created_on__ for o in orders])
..            max_created_on = max([o.__created_on__ for o in orders])
..            max_last_modified = max([o.__last_modified__ for o in orders])
..            create_duration = max_created_on - min_created_on
..            duration = max_last_modified - min_created_on
..            rate = len(command_ids) / float(duration)
..            period = 1 / rate
..            print("Orders created rate: {:.1f} order/s".format((len(command_ids) - 1) / create_duration))
..            print("Orders processed: {} orders in {:.3f}s at rate of {:.1f} "
..                  "orders/s, {:.3f}s each".format((len(command_ids) - 1), duration, rate, period))
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

Especially if cluster scaling is automated, it would be useful for processes to be distributed
automatically across the cluster. Actor model seems like a good foundation for such automation.


.. Todo: Make option to send event as prompt. Change Process to use event passed as prompt.

.. There are other ways in which the reliability could be relaxed. Persistence could be
.. optional. ...

Actor model
~~~~~~~~~~~

`beta`

An Actor model library, in particular the `Thespian Actor Library
<https://github.com/kquick/Thespian>`__, can be used to run
a pipelined system of process applications as actors.

The example below runs with Thespian's "simple system base".
The actors will run by sending messages recursively.

.. code:: python

    from eventsourcing.application.actors import ActorsRunner

    actors = ActorsRunner(system, pipeline_ids=pipeline_ids)

    with actors, Commands.mixin(SQLAlchemyApplication)() as commands:

        # Create new orders.
        command_ids = []
        for _ in range(num_orders_per_pipeline):
            for pipeline_id in pipeline_ids:

                # Change the pipeline for the command.
                commands.change_pipeline(pipeline_id)

                # Create a "create new order" command.
                cmd_id = commands.create_new_order()
                command_ids.append(cmd_id)

        # Check all commands are eventually done.
        for i, command_id in enumerate(command_ids):
            assert_command_is_done(commands.repository, command_id)

An Thespian "system base" other than the default "simple system base" can be
started by calling the functions ``start_multiproc_tcp_base_system()`` or
``start_multiproc_queue_base_system()`` before starting the system actors.

The base system can be shutdown by calling ``shutdown_actor_system()``, which
will shutdown any actors that are running in that base system.

With the "multiproc" base systems, the process application system actors will
be started in separate operating system processes. After they have been started,
they will continue to run until they are shutdown. The system actors can be started
by calling ``actors.start()``. The actors can be shutdown with ``actors.shutdown()``.

If ``actors`` is used as a context manager, as above, the ``start()`` method is
called when the context manager enters. The ``close()`` method is called
when the context manager exits. By default the ``shutdown()`` method
is not called by ``close()``. If ``ActorsRunner`` is constructed with ``shutdown_on_close=True``,
which is ``False`` by default, then the actors will be shutdown by ``close()``, and so
also when the context manager exits. Event so, shutting down the system actors will not
shutdown a "mutliproc" base system.

.. These methods can be used separately. A script can be called to initialise the base
.. system. Another script can start the system actors. Another script can be called to
.. send system commands, so that the system actors actually do some work. Another script
.. can be used to shutdown the system actors. And another can be used to shutdown the
.. base system. That may help operations. Please refer to the
.. `Thespian documentation <http://thespianpy.com/doc>`__ for more information about
.. `dynamic source loading <http://thespianpy.com/doc/in_depth.html>`__.

.. .. code:: python
..
..     actors.shutdown()
..
.. A system actor could start an actor for each pipeline-stage
.. when its address is requested, or otherwise make sure there is
.. one running actor for each process application-pipeline.
..
.. Actor processes could be automatically distributed across a cluster. The
.. cluster could auto-scale according to CPU usage (or perhaps network usage).
.. New nodes could run a container that begins by registering with the actor
.. system, (unless there isn't one, when it begins an election to become leader?)
.. and the actor system could run actors on it, reducing the load on other nodes.
..
.. Prompts from one process application-pipeline could be sent to another
.. as actor messages, rather than with a publish-subscribe service. The address
.. could be requested from the system, and the prompt sent directly.
..
.. To aid development and testing, actors could run without any
.. parallelism, for example with the "simpleSystemBase" actor
.. system in Thespian.
..
.. Scaling the system could be automated with the help of actors. A system actor
.. (started how? leader election? Kubernetes configuration?) could increase or
.. decrease the number of system pipelines, according to the rate at which events
.. are being added to the system command process, compared to the known (or measured)
.. rate at which commands can be processed by the system. If there are too many actors
.. dying from lack of work, then to reduce latency of starting an actor for each event
.. (extreme case), the number of pipelines could be reduced, so that there are enough
.. events to keep actors alive. If there are fewer pipelines than nodes, then some nodes
.. will have nothing to do, and can be easily removed from the cluster. A machine that
.. continues to run an actor could be more forcefully removed by killing the remaining
.. actors and restarting them elsewhere. Maybe heartbeats could be used to detect
.. when an actor has been killed and needs restarting? Maybe it's possible to stop
.. anything new from being started on a machine, so that it can eventually be removed
.. without force.


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

.. Although propagating application state by sending events as messages with actors doesn't
.. seem to offer a reliable way of projecting the state of an event-sourced application, actors
.. do seem like a great way of orchestrating a system of event-sourced process applications. The "based
.. on physics" thing seems to fit well with infrastructure, which is inherently imperfect.
.. We just don't need by default to instantiate unbounded nondeterminism for every concern
.. in the system. But since actors can fail and be restarted automatically, and since a process
.. application needs to be run by something. it seems that an actor and process process
.. applications-pipelines go well together. The process appliation-actor idea seems like a
.. much better idea that the aggregate-actor idea. Perhaps aggregates could also usefully be actors,
.. but an adapter would need to be coded to process messages as commands, to return pending events as
.. messages, and so on, to represent themselves as message, and so on. It can help to have many
.. threads running consecutively through an aggregate, especially readers. The consistency of the
.. aggregate state is protected with optimistic concurrency control. Wrapping an aggregate as
.. an actor won't speed things up, unless the actor is persistent, which uses resources. Aggregates
.. could be cached inside the process application-pipeline, especially if it is know that they will
.. probably be reused.

.. Todo: Method to fastforward an aggregate, by querying for and applying new events?



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
