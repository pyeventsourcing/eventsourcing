import os
import time
import unittest

import logging

from thespian.actors import ActorSystem

from eventsourcing.application.actors import Actors
from eventsourcing.application.system import System
from eventsourcing.tests.test_system import Orders, Payments, Reservations, create_new_order, set_db_uri


# logger = logging.getLogger('')
# logger.setLevel(logging.WARNING)
# ch = logging.StreamHandler()
# ch.setLevel(logging.WARNING)
# logger.addHandler(ch)


logcfg = {
    'version': 1,
    'formatters': {
        'normal': {
            'format': '%(levelname)-8s %(message)s'
        }
    },
    'handlers': {
        # 'h': {
        #     'class': 'logging.FileHandler',
        #     'filename': 'hello.log',
        #     'formatter': 'normal',
        #     'level': logging.INFO
        # }
    },
    'loggers': {
        # '': {'handlers': ['h'], 'level': logging.DEBUG}
    }
}


class TestActors(unittest.TestCase):

    def setUp(self):
        # Shutdown base actor system, if running.
        self.actor_system = None
        ActorSystem().shutdown()
        # Set environment.
        set_db_uri()
        # Define system.
        self.system = System(Orders | Reservations | Orders | Payments | Orders)

    def tearDown(self):
        # Unset environment.
        try:
            del (os.environ['DB_URI'])
        except KeyError:
            pass
        # Shutdown base actor system.
        if self.actor_system:
            self.actor_system.shutdown()

    def test_simple_system_base(self):
        self.start_actor_system()
        self.check_actors()

    def test_multiproc_tcp_base(self):
        self.start_multiproc_tcp_base_system()
        self.check_actors()

    def _test_multiproc_queue_base(self):
        self.start_multiproc_queue_base_system()
        self.check_actors()

    def check_actors(self, num_pipelines=3, num_orders_per_pipeline=5):

        pipeline_ids = list(range(num_pipelines))

        actors = Actors(self.system, pipeline_ids=pipeline_ids)

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

                # time.sleep(1)

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

    def start_multiproc_tcp_base_system(self):
        self.start_actor_system(system_base='multiprocTCPBase')

    def start_multiproc_queue_base_system(self):
        self.start_actor_system(system_base='multiprocQueueBase')

    def start_actor_system(self, system_base=None):
        self.actor_system = ActorSystem(
            systemBase=system_base,
            logDefs=logcfg,
            # transientUnique=bool(system_base)
        )
