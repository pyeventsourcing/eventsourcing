from eventsourcing.tests.sequenced_item_tests.test_django_record_manager import DjangoTestCase
from eventsourcing.tests.contrib_tests.paxos_tests.test_paxos_system import TestPaxosSystem
from eventsourcing.application.django import WithDjango


class TestPaxosSystemWithDjango(DjangoTestCase, TestPaxosSystem):
    process_class = WithDjango

    def close_connections_before_forking(self):
        # If connection is already made close it.
        from django.db import connection
        if connection.connection is not None:
            connection.close()

    def test_single_threaded(self):
        super(TestPaxosSystemWithDjango, self).test_single_threaded()

    def test_multiprocessing(self):
        super(TestPaxosSystemWithDjango, self).test_multiprocessing()
