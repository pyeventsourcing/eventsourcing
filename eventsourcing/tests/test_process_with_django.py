from eventsourcing.tests.sequenced_item_tests.test_django_record_manager import DjangoTestCase
from eventsourcing.application.django import DjangoApplication
from eventsourcing.tests.test_process import TestProcess


class TestProcessWithDjango(DjangoTestCase, TestProcess):
    process_class = DjangoApplication


del(TestProcess)
