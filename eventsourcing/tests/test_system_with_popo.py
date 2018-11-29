from unittest import skip

from eventsourcing.tests.sequenced_item_tests.test_popo_record_manager import PopoTestCase

from eventsourcing.application.popo import PopoApplication
from eventsourcing.tests.test_system import TestSystem


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
del (TestSystem)
