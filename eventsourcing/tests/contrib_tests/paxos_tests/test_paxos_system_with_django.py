from eventsourcing.tests.sequenced_item_tests.test_django_record_manager import DjangoTestCase
from eventsourcing.tests.contrib_tests.paxos_tests import test_paxos_system
from eventsourcing.application.django import DjangoApplication


class TestPaxosSystemWithDjango(DjangoTestCase, test_paxos_system.TestPaxosSystem):
    infrastructure_class = DjangoApplication
