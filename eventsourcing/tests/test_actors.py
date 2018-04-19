import os
import time
import unittest

from eventsourcing.application.actors import Actors
from eventsourcing.application.system import System
from eventsourcing.tests.test_system import Order, Orders, Payments, Reservations, create_new_order, set_db_uri


class TestActors(unittest.TestCase):

    def setUp(self):
        # Set up the database.
        set_db_uri()

        self.system = System(
            (Orders, Reservations, Orders, Payments, Orders),
        )


    def tearDown(self):
        try:
            del (os.environ['DB_URI'])
        except KeyError:
            pass

    def test_simpleSystemBase(self):
        # self.check_actors('simpleSystemBase', 1, 10)
        # self.check_actors('simpleSystemBase', 10, 1)
        self.check_actors('simpleSystemBase', 10, 10)

    def test_multiprocQueueBase(self):
        # This works.
        self.check_actors('multiprocQueueBase', 2, 4)
        # self.check_actors('multiprocQueueBase', 3, 1)
        # self.check_actors('multiprocQueueBase', 3, 3)
        # self.check_actors('multiprocQueueBase', 1, 15)

        # This is really slow.
        # self.check_actors('multiprocQueueBase', 2, 2)
        # self.check_actors('multiprocQueueBase', 2, 5)


    def test_multiprocTCPBase(self):
        # self.check_actors('multiprocTCPBase', 1, 1)
        # self.check_actors('multiprocTCPBase', 1, 3)
        self.check_actors('multiprocTCPBase', 3, 5)

    def _test_multiprocUDPBase(self):
        self.check_actors('multiprocUDPBase', 1, 1)

    def check_actors(self, actor_system_base, num_pipelines, num_orders_per_pipeline):

        pipeline_ids = list(range(num_pipelines))

        actors = Actors(self.system, pipeline_ids=pipeline_ids, actor_system_base=actor_system_base)

        # Todo: Use wakeupAfter() to poll for new notifications (see Timer Messages).
        # Todo: Fix multiple pipelines with multiproc bases.


        order_ids = []

        with Orders(setup_tables=True) as app, actors:
        # with actors:

            # Create some new orders.
            for _ in range(num_orders_per_pipeline):

                for pipeline_id in pipeline_ids:

                    app.change_pipeline(pipeline_id)

                    order_id = create_new_order()
                    order_ids.append(order_id)

                    time.sleep(0.05)

            # Wait for orders to be reserved and paid.
            retries = 100 + 100 * num_orders_per_pipeline * len(pipeline_ids)
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

