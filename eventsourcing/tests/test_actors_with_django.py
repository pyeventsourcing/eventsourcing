from eventsourcing.tests.sequenced_item_tests.test_django_record_manager import DjangoTestCase
from eventsourcing.application.django import WithDjango
from eventsourcing.tests.test_actors import TestActors


class TestActorsWithDjango(DjangoTestCase, TestActors):
    process_class = WithDjango
