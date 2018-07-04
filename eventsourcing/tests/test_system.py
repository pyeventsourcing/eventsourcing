import os
import time
from unittest import TestCase
from uuid import uuid4

from eventsourcing.application.multiprocess import Multiprocess
from eventsourcing.application.system import System
from eventsourcing.domain.model.events import assert_event_handlers_empty, clear_event_handlers
from eventsourcing.tests.test_process import ExampleAggregate
from eventsourcing.tests.test_system_fixtures import set_db_uri, Order, Reservation, Payment, create_new_order, Orders, Reservations, Payments, Examples


class TestSystem(TestCase):

    def test_singlethreaded_multiapp_system(self):
        system = System(
            Orders | Reservations | Orders,
            Orders | Payments | Orders,
            setup_tables=True
        )

        with system:
            # Create new Order aggregate.
            order_id = create_new_order()

            # Check the order is reserved and paid.
            repository = system.orders.repository
            assert repository[order_id].is_reserved
            assert repository[order_id].is_paid

    def test_multiprocessing_singleapp_system(self):
        system = System(Examples | Examples, setup_tables=True)

        set_db_uri()

        with Examples() as app, Multiprocess(system):
            aggregate = ExampleAggregate.__create__()
            aggregate.__save__()

            assert aggregate.id in app.repository

            # Check the aggregate is moved on.
            retries = 50
            while not app.repository[aggregate.id].is_moved_on:

                time.sleep(0.1)
                retries -= 1
                assert retries, "Failed to move"

    def test_multiprocessing_multiapp_system(self):

        set_db_uri()

        with Orders(setup_table=True) as app:
            # Create a new order.
            order_id = create_new_order()

            # Check new order exists in the repository.
            assert order_id in app.repository

        system = System(
            Orders | Reservations | Orders,
            Orders | Payments | Orders,
        )

        multiprocess = Multiprocess(system)

        # Start multiprocessing system.
        with multiprocess:

            with Orders() as app:

                retries = 50
                while not app.repository[order_id].is_reserved:
                    time.sleep(0.1)
                    retries -= 1
                    assert retries, "Failed set order.is_reserved"

                while retries and not app.repository[order_id].is_paid:
                    time.sleep(0.1)
                    retries -= 1
                    assert retries, "Failed set order.is_paid"

    def test_multipipeline_multiprocessing_multiapp(self):

        set_db_uri()

        system = System(
            (Orders, Reservations, Orders, Payments, Orders),
            setup_tables=True
        )

        num_pipelines = 3

        pipeline_ids = range(num_pipelines)

        multiprocess = Multiprocess(system, pipeline_ids=pipeline_ids)

        num_orders_per_pipeline = 5
        order_ids = []

        # Start multiprocessing system.
        with multiprocess, Orders(setup_table=True) as orders:

            # Create some new orders.
            for _ in range(num_orders_per_pipeline):

                for pipeline_id in pipeline_ids:

                    orders.change_pipeline(pipeline_id)

                    order_id = create_new_order()
                    order_ids.append(order_id)

                    time.sleep(0.05)

            # Wait for orders to be reserved and paid.
            retries = 10 + 10 * num_orders_per_pipeline * len(pipeline_ids)
            for i, order_id in enumerate(order_ids):

                while not orders.repository[order_id].is_reserved:
                    time.sleep(0.1)
                    retries -= 1
                    assert retries, "Failed set order.is_reserved {} ({})".format(order_id, i)

                while retries and not orders.repository[order_id].is_paid:
                    time.sleep(0.1)
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

    def test_payments_policy(self):
        # Prepare fake repository with a real Order aggregate.
        order = Order.__create__()
        fake_repository = {order.id: order}

        # Check policy makes payment whenever order is reserved.
        event = Order.Reserved(originator_id=order.id, originator_version=1)

        with Payments() as process:
            payment = process.policy(repository=fake_repository, event=event)
            assert isinstance(payment, Payment), payment
            assert payment.order_id == order.id

    def test_orders_policy(self):
        # Prepare fake repository with a real Order aggregate.
        order = Order.__create__()
        fake_repository = {order.id: order}

        # Check order is not reserved.
        assert not order.is_reserved

        # Reservation created.
        with Orders() as process:
            event = Reservation.Created(originator_id=uuid4(), originator_topic='', order_id=order.id)
            process.policy(repository=fake_repository, event=event)

        # Check order is reserved.
        assert order.is_reserved

    def tearDown(self):
        assert_event_handlers_empty()
        clear_event_handlers()
        try:
            del (os.environ['DB_URI'])
        except KeyError:
            pass


# Second example - orders, reservations, payments.


