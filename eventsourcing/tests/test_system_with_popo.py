from time import sleep, time, process_time
from unittest import skip

from eventsourcing.application.system import SteppingMultiThreadedRunner, System, SteppingSingleThreadedRunner
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

    def test_stepping_singlethreaded_runner_with_multiapp_system(self):
        system = System(
            Orders | Reservations | Orders,
            Orders | Payments | Orders,
            setup_tables=True,
            infrastructure_class=self.infrastructure_class
        )

        self.set_db_uri()

        normal_speed = 3
        scale_factor = 0
        runner = SteppingSingleThreadedRunner(
            system=system,
            normal_speed=normal_speed,
            scale_factor=scale_factor,
            # is_verbose=True,
        )

        start_time = time()
        start_process_time = process_time()

        with runner:

            orders = system.processes['orders']

            # Create a new order.
            num_orders = 120
            order_ids = []
            for i in range(num_orders):
                def cmd():
                    order_id = create_new_order()
                    assert order_id in orders.repository
                    order_ids.append(order_id)
                runner.call_in_future(cmd, 20 * (i + 1))
                # sleep(0.1)
                # sleep(tick_interval / 3)
                # sleep(tick_interval * 10)

            retries = 10 * num_orders
            while len(order_ids) < num_orders:
                sleep(0.01)

            for order_id in order_ids[-1:]:
                # while not orders.repository[order_id].is_reserved:
                #     sleep(0.1)
                #     retries -= 1
                #     assert retries, "Failed set order.is_reserved"

                while retries and not orders.repository[order_id].is_paid:
                    if not runner.clock_thread.is_alive():
                        self.fail("Clock thread died")
                    # else:
                    #     print("clock thread is alive")

                    # sleep(1)
                    sleep(0.2)
                    retries -= 1

        if runner.clock_thread.is_alive():
            self.fail("Clock thread still alive")
        final_time = runner.clock_thread.tick_count / runner.normal_speed
        print(f"Runner: average clock speed {runner.clock_thread.actual_clock_speed:.1f}Hz")
        print(f"Runner: total tick count {runner.clock_thread.tick_count}")
        print(f"Runner: total time in simulation {final_time:.2f}s")

        elapsed_time = time() - start_time
        print(f"Duration: { elapsed_time :.4f}s")
        execution_time = process_time() - start_process_time
        print(f"CPU: { 100 * execution_time / elapsed_time :.2f}%")

        assert retries, "Failed set order.is_paid"
        sleep(0.001)

    def test_stepping_multithreaded_runner_with_multiapp_system(self):
        system = System(
            Orders | Reservations | Orders,
            Orders | Payments | Orders,
            setup_tables=True,
            infrastructure_class=self.infrastructure_class
        )

        self.set_db_uri()

        normal_speed = 5
        scale_factor = 0
        runner = SteppingMultiThreadedRunner(
            system=system,
            normal_speed=normal_speed,
            scale_factor=scale_factor,
            is_verbose=False,
        )
        with runner:

            start_time = time()
            start_process_time = process_time()

            orders = system.processes['orders']

            # Create a new order.
            num_orders = 12
            order_ids = []
            for i in range(num_orders):
                def cmd():
                    order_id = create_new_order()
                    assert order_id in orders.repository
                    order_ids.append(order_id)
                runner.call_in_future(cmd, 20 * (i + 1))
                # sleep(0.1)
                # sleep(tick_interval / 3)
                # sleep(tick_interval * 10)

            while len(order_ids) < num_orders:
                sleep(0.01)

            retries = 10 * num_orders
            for order_id in order_ids[-1:]:
                # while not orders.repository[order_id].is_reserved:
                #     sleep(0.1)
                #     retries -= 1
                #     assert retries, "Failed set order.is_reserved"

                while retries and not orders.repository[order_id].is_paid:
                    # sleep(1)
                    sleep(0.2)
                    retries -= 1

        final_time = runner.clock_thread.tick_count / runner.normal_speed
        print(f"Runner: average clock speed {runner.clock_thread.actual_clock_speed:.0f}Hz")
        print(f"Runner: total tick count {runner.clock_thread.tick_count}")
        print(f"Runner: total time in simulation {final_time:.2f}s")

        elapsed_time = time() - start_time
        print(f"Duration: { elapsed_time :.4f}s")
        execution_time = process_time() - start_process_time
        print(f"CPU: { 100 * execution_time / elapsed_time :.2f}%")

        assert retries, "Failed set order.is_paid"

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
