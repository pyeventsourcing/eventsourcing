from eventsourcing.tests.sequenced_item_tests.test_django_record_manager import DjangoTestCase
from eventsourcing.tests.contrib_tests.paxos_tests.test_paxos_system import TestPaxosSystem
from eventsourcing.application.django import WithDjango
from eventsourcing.infrastructure.django.utils import close_django_connection


class TestPaxosSystemWithDjango(DjangoTestCase, TestPaxosSystem):
    process_class = WithDjango
