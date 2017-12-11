from eventsourcing.tests.example_application_tests.base import ExampleApplicationTestCase
from eventsourcing.tests.sequenced_item_tests.test_django_active_record_strategy import \
    DjangoTestCase


class TestExampleApplicationWithDjango(DjangoTestCase, ExampleApplicationTestCase):
    def construct_log_active_record_strategy(self):
        return self.construct_entity_active_record_strategy()
