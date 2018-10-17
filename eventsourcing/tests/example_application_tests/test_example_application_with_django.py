from eventsourcing.tests.example_application_tests import base
from eventsourcing.tests.sequenced_item_tests.test_django_record_manager import DjangoTestCase


class TestExampleApplicationWithDjango(DjangoTestCase, base.ExampleApplicationTestCase):
    def construct_log_record_manager(self):
        return self.construct_entity_record_manager()

    def construct_entity_record_manager(self):
        return self.factory.construct_integer_sequenced_record_manager()

