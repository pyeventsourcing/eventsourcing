from eventsourcing.tests.sequenced_item_tests.test_django_record_manager import DjangoTestCase
from eventsourcing.tests.contrib_tests.paxos_tests.test_paxos_system import TestPaxosSystem
from eventsourcing.application.django import DjangoApplication


class TestPaxosSystemWithDjango(DjangoTestCase, TestPaxosSystem):
    infrastructure_class = DjangoApplication
