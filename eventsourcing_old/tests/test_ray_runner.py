import logging
import os
import sys
import time
import unittest
from time import sleep
from unittest import skipIf
from uuid import UUID

import ray

from eventsourcing.application.popo import PopoApplication
from eventsourcing.application.sqlalchemy import SQLAlchemyApplication
from eventsourcing.domain.model.events import (
    assert_event_handlers_empty,
    clear_event_handlers,
)
from eventsourcing.system.definition import System
from eventsourcing.system.ray import RayProcess, RayRunner
from eventsourcing.system.rayhelpers import RayPrompt
from eventsourcing.tests.system_test_fixtures import (
    Orders,
    Payments,
    Reservations,
    set_db_uri,
)

logger = logging.getLogger("")
logger.setLevel(logging.ERROR)
ch = logging.StreamHandler()
ch.setLevel(logging.ERROR)
logger.addHandler(ch)


@skipIf(
    sys.version_info[:2] == (3, 6), "RayRunner not working with Python36 (pickle issue)"
)
# Seems to be doing something with a prompt, and type checking from annotation.
# It works in python3.7...
#
# Traceback (most recent call last):
#   File "...tests/test_ray_runner.py", line 61, in test_ray_runner
#     self.check_actors()
#   File "...tests/test_ray_runner.py", line 74, in check_actors
#     with runner:
#   File "...system/definition.py", line 236, in __enter__
#     self.start()
#   File "...system/ray.py", line 89, in start
#     setup_tables=self.setup_tables,
#   File "...ray/actor.py", line 326, in remote
#     return self._remote(args=args, kwargs=kwargs)
#   File "...ray/actor.py", line 479, in _remote
#     meta.modified_class, meta.actor_method_names)
#   File "...ray/function_manager.py", line 578, in export_actor_class
#     "class": pickle.dumps(Class),
#   File "...ray/cloudpickle/cloudpickle_fast.py", line 68, in dumps
#     cp.dump(obj)
#   File "...ray/cloudpickle/cloudpickle_fast.py", line 557, in dump
#     return Pickler.dump(self, obj)
# _pickle.PicklingError: Can't pickle typing.Union[
# eventsourcing.application.process.Prompt, NoneType]: it's not the same object as
# typing.Union


class TestRayRunner(unittest.TestCase):
    infrastructure_class = SQLAlchemyApplication
    # infrastructure_class = PopoApplication

    def setUp(self):
        # Define system.
        self.system = System(
            Orders | Reservations | Orders | Payments | Orders,
            infrastructure_class=self.infrastructure_class,
        )
        # Set environment.
        set_db_uri()

    def tearDown(self):
        # Unset environment.
        try:
            del os.environ["DB_URI"]
        except KeyError:
            pass

        try:
            assert_event_handlers_empty()
        finally:
            clear_event_handlers()

    def test_ray_runner(self):
        self.check_actors(2, 60)

    def check_actors(self, num_pipelines=1, num_orders_per_pipeline=10):

        pipeline_ids = list(range(num_pipelines))

        db_uri = os.environ.get("DB_URI", None)
        runner = RayRunner(
            self.system, pipeline_ids=pipeline_ids, setup_tables=True, db_uri=db_uri
        )

        num_orders = num_pipelines * num_orders_per_pipeline

        with runner:

            sleep(0.2)

            # Create some new orders.
            order_ids = []
            for i in range(num_orders):

                pipeline_id = i % len(pipeline_ids)
                order_id = runner.get(Orders, pipeline_id).create_new_order()
                order_ids.append(order_id)
                sleep(0.001)

            # Wait for orders to be reserved and paid.

            retries = 20 + 10 * num_orders
            for i, order_id in enumerate(order_ids):

                pipeline_id = i % len(pipeline_ids)

                orders = runner.get(Orders, pipeline_id)
                while not orders.is_order_reserved(order_id):
                    time.sleep(0.5)
                    retries -= 1
                    assert retries, "Failed set order.is_reserved {} ({})".format(
                        order_id, i
                    )

                while not orders.is_order_paid(order_id):
                    time.sleep(0.5)
                    retries -= 1
                    assert retries, "Failed set order.is_paid ({})".format(i)

                # print(i, "Completed order", order_id)

            if not order_ids:
                return

            # Calculate timings from event timestamps.
            orders = []
            for i, order_id in enumerate(order_ids):
                pipeline_id = i % len(pipeline_ids)
                orders.append(runner.get(Orders, pipeline_id).get_order(order_id))
            first_timestamp = min([o.__created_on__ for o in orders])
            last_timestamp = max([o.__last_modified__ for o in orders])
            duration = last_timestamp - first_timestamp
            rate = len(order_ids) / float(duration)
            period = 1 / rate
            print(
                "Orders system processed {} orders in {:.3f}s at rate of {:.1f} "
                "orders/s, {:.3f}s each".format(len(order_ids), duration, rate, period)
            )

            # Print min, average, max duration.
            durations = [o.__last_modified__ - o.__created_on__ for o in orders]
            print("Min order processing time: {:.3f}s".format(min(durations)))
            print(
                "Mean order processing time: {:.3f}s".format(
                    sum(durations) / len(durations)
                )
            )
            print("Max order processing time: {:.3f}s".format(max(durations)))

            sleep(0)


class TestRayProcess(unittest.TestCase):
    infrastructure_class = SQLAlchemyApplication

    def test_ray_process(self):
        # Create process with Orders application.
        ray_orders_process = RayProcess.remote(
            application_process_class=Orders,
            infrastructure_class=self.infrastructure_class,
            setup_tables=True,
        )

        # Initialise the ray process.
        ray.get(ray_orders_process.init.remote({}, {}))

        # Create a new order, within the ray process.
        order_id = ray.get(ray_orders_process.call.remote("create_new_order"))

        # Check a UUID is returned.
        self.assertIsInstance(order_id, UUID)

        # Get range of notifications.
        notifications = ray.get(ray_orders_process.get_notifications.remote(1, 1000))
        self.assertIsInstance(notifications, list)
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0]["id"], 1)

        # Check the range is working.
        notifications = ray.get(ray_orders_process.get_notifications.remote(2, 2))
        self.assertIsInstance(notifications, list)
        self.assertEqual(len(notifications), 0, notifications)

        # Create process with Reservations application.
        ray_reservations_process = RayProcess.remote(
            application_process_class=Reservations,
            infrastructure_class=self.infrastructure_class,
            setup_tables=True,
        )
        # Make the reservations follow the orders.
        ray.get(
            ray_reservations_process.init.remote({"orders": ray_orders_process}, {})
        )

        # Get range of notifications.
        notifications = ray.get(
            ray_reservations_process.get_notifications.remote(1, 1000)
        )
        self.assertIsInstance(notifications, list)
        self.assertEqual(len(notifications), 0)

        # Prompt the process.
        prompt = RayPrompt("orders", 0)
        rayid = ray_reservations_process.prompt.remote(prompt)
        ray.get(rayid)

        # Check a reservation was created.
        retries = 10
        while retries:
            sleep(0.1)
            # Get range of notifications.
            notifications = ray.get(
                ray_reservations_process.get_notifications.remote(1, 1000)
            )
            self.assertIsInstance(notifications, list)

            try:
                self.assertEqual(len(notifications), 1)
            except AssertionError:
                if retries:
                    retries -= 1
                    print("Retrying...", retries)
                else:
                    raise
            else:
                break

        # Add reservations as downstream process of orders.
        ray_orders_process.add_downstream_process.remote(
            "reservations", ray_reservations_process
        )

        # Create a new order, within the ray process.
        order_id = ray.get(ray_orders_process.call.remote("create_new_order"))

        # Get range of notifications.
        notifications = ray.get(ray_orders_process.get_notifications.remote(1, 1000))
        self.assertIsInstance(notifications, list)
        self.assertEqual(len(notifications), 2)

        # Check another reservation was created.
        retries = 10
        while True:
            sleep(0.1)
            # Get a section of the notification log.
            # Get range of notifications.
            notifications = ray.get(
                ray_reservations_process.get_notifications.remote(1, 1000)
            )
            self.assertIsInstance(notifications, list)

            try:
                self.assertEqual(len(notifications), 2)
            except AssertionError:
                if retries:
                    retries -= 1
                    print("Retrying...", retries)
                else:
                    raise
            else:
                break

        # Todo: More of this...

        # reader = NotificationLogReader(
        #     notification_log=RayNotificationLog(
        #         upstream_process=ray_process
        #     ),
        # )
        # notifications = list(reader.read())
        # self.assertEqual(len(notifications), 1)
        # created_event_notification = notifications[0]
        # self.assertEqual(created_event_notification['id'], 1)
        # self.assertEqual(created_event_notification['originator_id'], order_id)
        # self.assertEqual(created_event_notification['originator_version'], 0)
