import os
from time import sleep, time
from unittest import TestCase
from uuid import uuid4

from eventsourcing.application.multiprocess import MultiprocessRunner
from eventsourcing.application.sqlalchemy import SQLAlchemyApplication
from eventsourcing.application.system import MultiThreadedRunner, System
from eventsourcing.domain.model.events import assert_event_handlers_empty, clear_event_handlers
from eventsourcing.tests.test_process import ExampleAggregate
from eventsourcing.tests.test_system_fixtures import Examples, Order, Orders, Payment, Payments, Reservation, \
    Reservations, create_new_order, set_db_uri


class TestSystem(TestCase):
    infrastructure_class = SQLAlchemyApplication

    def test_singlethreaded_runner_with_multiapp_system(self):
        system = System(Orders | Reservations | Orders,
                        Orders | Payments | Orders,
                        setup_tables=True,
                        infrastructure_class=self.infrastructure_class
                        )

        with system:
            # Create new Order aggregate.
            order_id = create_new_order()

            # Check the order is reserved and paid.
            repository = system.processes['orders'].repository
            assert repository[order_id].is_reserved
            assert repository[order_id].is_paid

    def test_multithreaded_runner_with_singleapp_system(self):

        system = System(Examples | Examples,
                        setup_tables=True,
                        infrastructure_class=self.infrastructure_class)

        self.set_db_uri()

        with MultiThreadedRunner(system):

            app = system.processes['examples']

            aggregate = ExampleAggregate.__create__()
            aggregate.__save__()

            assert aggregate.id in app.repository

            # Check the aggregate is moved on.
            retries = 50
            while not app.repository[aggregate.id].is_moved_on:

                sleep(0.1)
                retries -= 1
                assert retries, "Failed to move"

    def test_multithreaded_runner_with_multiapp_system(self):
        system = System(
            Orders | Reservations | Orders,
            Orders | Payments | Orders,
            setup_tables=True,
            infrastructure_class=self.infrastructure_class
        )

        self.set_db_uri()

        with MultiThreadedRunner(system):

            started = time()

            orders = system.processes['orders']

            # Create new orders.
            num_orders = 10
            order_ids = []
            for i in range(num_orders):
                order_id = create_new_order()
                order_ids.append(order_id)

            retries = num_orders
            for order_id in order_ids:
                # while not orders.repository[order_id].is_reserved:
                #     sleep(0.1)
                #     retries -= 1
                #     assert retries, "Failed set order.is_reserved"

                while retries and not orders.repository[order_id].is_paid:
                    sleep(0.1)
                    retries -= 1
                    assert retries, "Failed set order.is_paid"

            print(f"Duration: { time() - started :.4f}s")

    def test_clocked_multithreaded_runner_with_multiapp_system(self):
        system = System(
            Orders | Reservations | Orders,
            Orders | Payments | Orders,
            setup_tables=True,
            infrastructure_class=self.infrastructure_class
        )

        self.set_db_uri()

        clock_speed = 10
        tick_interval = 1 / clock_speed
        with MultiThreadedRunner(system, clock_speed=clock_speed):

            started = time()

            orders = system.processes['orders']

            # Create a new order.
            num_orders = 10
            order_ids = []
            for i in range(num_orders):
                order_id = create_new_order()
                order_ids.append(order_id)
                # sleep(tick_interval / 3)
                # sleep(tick_interval * 10)

            retries = 10 * num_orders
            for order_id in order_ids:
                # while not orders.repository[order_id].is_reserved:
                #     sleep(0.1)
                #     retries -= 1
                #     assert retries, "Failed set order.is_reserved"

                while retries and not orders.repository[order_id].is_paid:
                    sleep(0.1)
                    retries -= 1
                    assert retries, "Failed set order.is_paid"

        print(f"Duration: { time() - started :.4f}s")

    def test_multiprocessing_singleapp_system(self):

        system = System(Examples | Examples,
                        setup_tables=True,
                        infrastructure_class=self.infrastructure_class)

        self.set_db_uri()

        self.close_connections_before_forking()

        with MultiprocessRunner(system), system.construct_app(Examples) as app:

            aggregate = ExampleAggregate.__create__()
            aggregate.__save__()

            assert aggregate.id in app.repository

            # Check the aggregate is moved on.
            retries = 50
            while not app.repository[aggregate.id].is_moved_on:

                sleep(0.1)
                retries -= 1
                assert retries, "Failed to move"

    def test_multiprocessing_multiapp_system(self):
        system = System(
            Orders | Reservations | Orders,
            Orders | Payments | Orders,
            setup_tables=True,
            infrastructure_class=self.infrastructure_class
        )

        self.set_db_uri()

        with system.construct_app(Orders) as app:
            # Create a new order.
            order_id = create_new_order()
            # Check new order exists in the repository.
            assert order_id in app.repository

        self.close_connections_before_forking()

        with MultiprocessRunner(system):

            with system.construct_app(Orders) as app:
                retries = 50
                while not app.repository[order_id].is_reserved:
                    sleep(0.1)
                    retries -= 1
                    assert retries, "Failed set order.is_reserved"

                while retries and not app.repository[order_id].is_paid:
                    sleep(0.1)
                    retries -= 1
                    assert retries, "Failed set order.is_paid"

    def test_multipipeline_multiprocessing_multiapp(self):

        self.set_db_uri()

        system = System(
            (Orders, Reservations, Orders, Payments, Orders),
            setup_tables=True,
            infrastructure_class=self.infrastructure_class
        )

        num_pipelines = 2

        pipeline_ids = range(num_pipelines)

        multiprocess = MultiprocessRunner(system, pipeline_ids=pipeline_ids)

        num_orders_per_pipeline = 5
        order_ids = []

        self.close_connections_before_forking()

        # Start multiprocessing system.
        with multiprocess, system.construct_app(Orders) as orders:

            # Create some new orders.
            for _ in range(num_orders_per_pipeline):

                for pipeline_id in pipeline_ids:

                    orders.change_pipeline(pipeline_id)

                    order_id = create_new_order()
                    order_ids.append(order_id)

                    sleep(0.05)

            # Wait for orders to be reserved and paid.
            retries = 10 + 10 * num_orders_per_pipeline * len(pipeline_ids)
            for i, order_id in enumerate(order_ids):

                while not orders.repository[order_id].is_reserved:
                    sleep(0.1)
                    retries -= 1
                    assert retries, "Failed set order.is_reserved {} ({})".format(order_id, i)

                while retries and not orders.repository[order_id].is_paid:
                    sleep(0.1)
                    retries -= 1
                    assert retries, "Failed set order.is_paid ({})".format(i)

            # Calculate timings from event timestamps.
            order_aggregates = [orders.repository[oid] for oid in order_ids]
            first_timestamp = min([o.__created_on__ for o in order_aggregates])
            last_timestamp = max([o.__last_modified__ for o in order_aggregates])
            duration = last_timestamp - first_timestamp
            rate = len(order_ids) / float(duration)
            period = 1 / rate
            print("Orders system processed {} orders in {:.3f}s at rate of {:.1f} "
                  "orders/s, {:.3f}s each".format(len(order_ids), duration, rate, period))

            # Print min, average, max duration.
            durations = [o.__last_modified__ - o.__created_on__ for o in order_aggregates]
            print("Min order processing time: {:.3f}s".format(min(durations)))
            print("Mean order processing time: {:.3f}s".format(sum(durations) / len(durations)))
            print("Max order processing time: {:.3f}s".format(max(durations)))

    def set_db_uri(self):
        set_db_uri()

    def close_connections_before_forking(self):
        # Used for closing Django connection before multiprocessing module forks the OS process.
        pass

    def test_payments_policy(self):
        # Prepare fake repository with a real Order aggregate.
        order = Order.__create__()
        fake_repository = {order.id: order}

        # Check policy makes payment whenever order is reserved.
        event = Order.Reserved(originator_id=order.id, originator_version=1)

        payment = Payments.policy(repository=fake_repository, event=event)
        assert isinstance(payment, Payment), payment
        assert payment.order_id == order.id

    def test_orders_policy(self):
        # Prepare fake repository with a real Order aggregate.
        order = Order.__create__()
        fake_repository = {order.id: order}

        # Check order is not reserved.
        assert not order.is_reserved

        # Reservation created.
        event = Reservation.Created(originator_id=uuid4(), originator_topic='', order_id=order.id)
        Orders.policy(repository=fake_repository, event=event)

        # Check order is reserved.
        assert order.is_reserved

    def tearDown(self):
        assert_event_handlers_empty()
        clear_event_handlers()
        try:
            del (os.environ['DB_URI'])
        except KeyError:
            pass
