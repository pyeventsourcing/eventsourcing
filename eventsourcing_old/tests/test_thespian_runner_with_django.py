from eventsourcing.application.django import DjangoApplication
from eventsourcing.tests.sequenced_item_tests.test_django_record_manager import (
    DjangoTestCase,
)
from eventsourcing.tests.test_thespian_runner import TestThespianRunner


class TestThespianRunnerWithDjango(DjangoTestCase, TestThespianRunner):
    infrastructure_class = DjangoApplication
