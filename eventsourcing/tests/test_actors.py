import logging
import os
import time
import unittest
from unittest import skip

from eventsourcing.application.actors import ActorModelRunner, shutdown_actor_system, start_actor_system, \
    start_multiproc_tcp_base_system
from eventsourcing.application.sqlalchemy import SQLAlchemyApplication
from eventsourcing.application.system import System
from eventsourcing.domain.model.events import assert_event_handlers_empty, clear_event_handlers
from eventsourcing.tests.test_system_fixtures import Orders, Payments, Reservations, create_new_order, set_db_uri

logger = logging.getLogger('')
logger.setLevel(logging.ERROR)
ch = logging.StreamHandler()
ch.setLevel(logging.ERROR)
logger.addHandler(ch)


class TestActors(unittest.TestCase):
    infrastructure_class = SQLAlchemyApplication

    def setUp(self):
        # Set environment.
        set_db_uri()
        # Define system.
        self.system = System(Orders | Reservations | Orders | Payments | Orders,
                             infrastructure_class=self.infrastructure_class)

    def test_simple_system_base(self):
        start_actor_system()
        self.check_actors()

    @skip("Having trouble running Thespian's 'multiproc tcp base'")
    def test_multiproc_tcp_base(self):
        start_multiproc_tcp_base_system()
        self.check_actors()

    def close_connections_before_forking(self):
        # Used for closing Django connection before multiprocessing module forks the OS process.
        pass

    def check_actors(self, num_pipelines=3, num_orders_per_pipeline=5):

        pipeline_ids = list(range(num_pipelines))

        self.close_connections_before_forking()

        actors = ActorModelRunner(self.system, pipeline_ids=pipeline_ids, shutdown_on_close=True)

        # Todo: Use wakeupAfter() to poll for new notifications (see Timer Messages).

        order_ids = []

        with self.system.construct_app(Orders, setup_table=True) as app, actors:

            # Create some new orders.
            for _ in range(num_orders_per_pipeline):

                for pipeline_id in pipeline_ids:
                    app.change_pipeline(pipeline_id)

                    order_id = create_new_order()
                    order_ids.append(order_id)

            # Wait for orders to be reserved and paid.
            retries = 20 + 10 * num_orders_per_pipeline * len(pipeline_ids)
            for i, order_id in enumerate(order_ids):

                while not app.repository[order_id].is_reserved:
                    time.sleep(0.1)
                    retries -= 1
                    assert retries, "Failed set order.is_reserved {} ({})".format(order_id, i)

                while retries and not app.repository[order_id].is_paid:
                    time.sleep(0.1)
                    retries -= 1
                    assert retries, "Failed set order.is_paid ({})".format(i)

            # Calculate timings from event timestamps.
            orders = [app.repository[oid] for oid in order_ids]
            first_timestamp = min([o.__created_on__ for o in orders])
            last_timestamp = max([o.__last_modified__ for o in orders])
            duration = last_timestamp - first_timestamp
            rate = len(order_ids) / float(duration)
            period = 1 / rate
            print("Orders system processed {} orders in {:.3f}s at rate of {:.1f} "
                  "orders/s, {:.3f}s each".format(len(order_ids), duration, rate, period))

            # Print min, average, max duration.
            durations = [o.__last_modified__ - o.__created_on__ for o in orders]
            print("Min order processing time: {:.3f}s".format(min(durations)))
            print("Mean order processing time: {:.3f}s".format(sum(durations) / len(durations)))
            print("Max order processing time: {:.3f}s".format(max(durations)))

    def tearDown(self):
        # Unset environment.
        try:
            del (os.environ['DB_URI'])
        except KeyError:
            pass

        try:
            # Shutdown base actor system.
            shutdown_actor_system()
        finally:
            # Clear event handlers.
            try:
                assert_event_handlers_empty()
            finally:
                clear_event_handlers()
