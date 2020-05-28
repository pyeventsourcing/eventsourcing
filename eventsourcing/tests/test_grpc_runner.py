import logging
from datetime import datetime
from time import sleep
from unittest import TestCase
from uuid import UUID

from eventsourcing.application.popo import PopoApplication
from eventsourcing.application.sqlalchemy import SQLAlchemyApplication
from eventsourcing.system.definition import System
from eventsourcing.system.grpcrunner.runner import GrpcRunner
from eventsourcing.tests.system_test_fixtures import Orders, Payments, Reservations


logging.basicConfig()


class TestGrpcRunner(TestCase):
    def test(self):
        timer_started = datetime.now()
        runner = GrpcRunner(
            System(Orders | Reservations | Orders | Payments | Orders),
            push_prompt_interval=0.2,
            infrastructure_class=PopoApplication,
            # infrastructure_class=SQLAlchemyApplication,
            setup_tables=True,
            use_individual_databases=False,
        )
        with runner:
            orders_client = runner.get(Orders)
            listener = runner.listen("test", [orders_client.client])

            startup_duration = (datetime.now() - timer_started).total_seconds()
            print("Start duration: %ss" % (startup_duration))

            num_orders = 2000
            order_ids = []
            timer_started = datetime.now()
            for i in range(num_orders):
                order_id = orders_client.create_new_order()
                assert isinstance(order_id, UUID)
                order_ids.append(order_id)

            started = datetime.now()
            while True:
                if orders_client.is_order_paid(order_ids[-1]):
                    break
                elif listener.prompt_events["orders"].wait(timeout=1):
                    listener.prompt_events["orders"].clear()
                elif (datetime.now() - started).total_seconds() > num_orders:
                    self.fail("Timed out waiting for orders to be paid")

            print(
                "Orders per second: %d"
                % (num_orders / (datetime.now() - timer_started).total_seconds())
            )
