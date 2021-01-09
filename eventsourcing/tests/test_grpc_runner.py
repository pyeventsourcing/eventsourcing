from datetime import datetime
from unittest import TestCase
from uuid import UUID

from eventsourcing.application.popo import PopoApplication
from eventsourcing.system.definition import System
from eventsourcing.system.grpc.runner import GrpcRunner
from eventsourcing.tests.system_test_fixtures import Orders, Payments, Reservations


class TestGrpcRunner(TestCase):
    def test(self):
        timer_started = datetime.now()
        runner = GrpcRunner(
            System(Orders | Reservations | Orders | Payments | Orders),
            pipeline_ids=[0, 1],
            infrastructure_class=PopoApplication,
            setup_tables=True,
            push_prompt_interval=0.1,
        )
        with runner:
            orders_client_0 = runner.get(Orders, 0)
            orders_client_1 = runner.get(Orders, 1)
            listener_0 = runner.listen("test", [orders_client_0.client])
            listener_1 = runner.listen("test", [orders_client_1.client])

            startup_duration = (datetime.now() - timer_started).total_seconds()
            print("Start duration: %ss" % (startup_duration))

            num_orders = 2000
            order_ids = []
            timer_started = datetime.now()
            for i in range(num_orders):
                order_id = orders_client_0.create_new_order()
                assert isinstance(order_id, UUID)
                order_ids.append(order_id)
                order_id = orders_client_1.create_new_order()
                assert isinstance(order_id, UUID)
                order_ids.append(order_id)

            started = datetime.now()
            while True:
                if orders_client_0.is_order_paid(order_ids[-2]):
                    break
                elif listener_0.prompt_events["orders"].wait(timeout=.1):
                    listener_0.prompt_events["orders"].clear()
                elif (datetime.now() - started).total_seconds() > num_orders:
                    self.fail("Timed out waiting for orders to be paid")
                if orders_client_1.is_order_paid(order_ids[-1]):
                    break
                elif listener_1.prompt_events["orders"].wait(timeout=.1):
                    listener_1.prompt_events["orders"].clear()
                elif (datetime.now() - started).total_seconds() > num_orders:
                    self.fail("Timed out waiting for orders to be paid")

            print(
                "Orders per second: %d"
                % (len(order_ids) / (datetime.now() - timer_started).total_seconds())
            )
