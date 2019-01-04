from eventsourcing.tests.sequenced_item_tests.test_django_record_manager import DjangoTestCase

from eventsourcing.application.django import DjangoApplication
from eventsourcing.tests.test_system import TestSystem


class TestSystemWithDjango(DjangoTestCase, TestSystem):
    infrastructure_class = DjangoApplication

    def test_multiprocessing_multiapp_system(self):
        super(TestSystemWithDjango, self).test_multiprocessing_multiapp_system()

    def set_db_uri(self):
        # The Django settings module doesn't currently recognise DB_URI.
        pass


# Avoid running imported test case.
del (TestSystem)
