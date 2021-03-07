from time import sleep

from django.core.management import call_command

from eventsourcing.application.django import DjangoApplication
from eventsourcing.tests.sequenced_item_tests.test_django_record_manager import (
    DjangoTestCase,
)
from eventsourcing.tests.test_system import TestSystem


class TestSystemWithDjango(DjangoTestCase, TestSystem):
    infrastructure_class = DjangoApplication

    def test_multiprocessing_multiapp_system(self):
        super(TestSystemWithDjango, self).test_multiprocessing_multiapp_system()

    def set_db_uri(self):
        # The Django settings module doesn't currently recognise DB_URI.
        pass


class SecondaryDjangoApplication(DjangoApplication):

    def construct_infrastructure(self):
        super(SecondaryDjangoApplication, self).construct_infrastructure(db_alias='secondary')


class TestSystemWithSecondaryDBDjango(DjangoTestCase, TestSystem):
    infrastructure_class = SecondaryDjangoApplication
    databases = ["secondary", "default"]

    def setUp(self):
        super(DjangoTestCase, self).setUp()
        call_command("migrate", database="secondary", verbosity=0, interactive=False)
        sleep(1)


# Avoid running imported test case.
del TestSystem
