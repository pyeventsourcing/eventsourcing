from unittest import skip

from eventsourcing.tests.sequenced_item_tests.test_popo_record_manager import PopoTestCase
from eventsourcing.tests.contrib_tests.paxos_tests import test_paxos_system
from eventsourcing.application.popo import PopoApplication


class TestPaxosSystemWithPopo(PopoTestCase, test_paxos_system.TestPaxosSystem):
    infrastructure_class = PopoApplication

    @skip("Popo doesn't do multiprocessing")
    def test_multiprocessing_performance(self):
        pass

    @skip("Popo doesn't do multiprocessing")
    def test_multiprocessing(self):
        pass
