from eventsourcing.tests.sequenced_item_tests.test_django_record_manager import DjangoTestCase
from eventsourcing.tests.contrib_tests.paxos_tests.test_paxos_system import TestPaxosSystem
from eventsourcing.application.django import WithDjango
from eventsourcing.infrastructure.django.utils import close_django_connection


class TestPaxosSystemWithDjango(DjangoTestCase, TestPaxosSystem):
    process_class = WithDjango

    def close_connections_before_forking(self):
        close_django_connection()

    def test_single_threaded(self):
        super(TestPaxosSystemWithDjango, self).test_single_threaded()

    def test_multiprocessing(self):
        super(TestPaxosSystemWithDjango, self).test_multiprocessing()
