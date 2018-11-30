import time
from time import sleep
from unittest import skip

from eventsourcing.application.system import BarrierControlledMultiThreadedRunner, System
from eventsourcing.tests.sequenced_item_tests.test_popo_record_manager import PopoTestCase

from eventsourcing.application.popo import PopoApplication
from eventsourcing.tests.test_system import TestSystem
from eventsourcing.tests.test_system_fixtures import create_new_order, Orders, Reservations, Payments


class TestSystemWithPopo(PopoTestCase, TestSystem):
    infrastructure_class = PopoApplication

    def test_singlethreaded_runner_with_multiapp_system(self):
        super(TestSystemWithPopo, self).test_singlethreaded_runner_with_multiapp_system()

    def test_multithreaded_runner_with_singleapp_system(self):
        super(TestSystemWithPopo, self).test_multithreaded_runner_with_singleapp_system()

    def test_multithreaded_runner_with_multiapp_system(self):
        super(TestSystemWithPopo, self).test_multithreaded_runner_with_multiapp_system()

    def test_clocked_multithreaded_runner_with_multiapp_system(self):
        super(TestSystemWithPopo, self).test_clocked_multithreaded_runner_with_multiapp_system()

    def test_barrier_controlled_multithreaded_runner_with_multiapp_system(self):
        system = System(
            Orders | Reservations | Orders,
            Orders | Payments | Orders,
            setup_tables=True,
            infrastructure_class=self.infrastructure_class
        )

        self.set_db_uri()

        normal_speed = 1
        scale_factor = 0
        runner = BarrierControlledMultiThreadedRunner(
            system=system,
            normal_speed=normal_speed,
            scale_factor=scale_factor
        )
        with runner:

            started = time.time()

            orders = system.processes['orders']

            # Create a new order.
            num_orders = 3000
            order_ids = []
            for i in range(num_orders):
                order_id = create_new_order()
                assert order_id in orders.repository
                order_ids.append(order_id)
                sleep(.2)
                # sleep(tick_interval / 3)
                # sleep(tick_interval * 10)

            retries = 10 * num_orders
            for order_id in order_ids[-1:]:
                # while not orders.repository[order_id].is_reserved:
                #     time.sleep(0.1)
                #     retries -= 1
                #     assert retries, "Failed set order.is_reserved"

                while retries and not orders.repository[order_id].is_paid:
                    time.sleep(1)
                    # time.sleep(0.2)
                    retries -= 1
                    assert retries, "Failed set order.is_paid"

        print(f"Duration: { time.time() - started :.4f}s")


    @skip("Popo record manager doesn't support multiprocessing")
    def test_multiprocessing_multiapp_system(self):
        super(TestSystemWithPopo, self).test_multiprocessing_multiapp_system()

    @skip("Popo record manager doesn't support multiprocessing")
    def test_multiprocessing_singleapp_system(self):
        super(TestSystemWithPopo, self).test_multiprocessing_singleapp_system()

    @skip("Popo record manager doesn't support multiprocessing")
    def test_multipipeline_multiprocessing_multiapp(self):
        super(TestSystemWithPopo, self).test_multipipeline_multiprocessing_multiapp()

    def set_db_uri(self):
        # The Popo settings module doesn't currently recognise DB_URI.
        pass


# Avoid running imported test case.
del TestSystem
