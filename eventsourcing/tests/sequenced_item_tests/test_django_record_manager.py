import os

os.environ['DJANGO_SETTINGS_MODULE'] = 'eventsourcing.tests.djangoproject.djangoproject.settings'

import django

django.setup()

import unittest
from time import sleep

from django.core.management import call_command
from django.test import TransactionTestCase

from eventsourcing.infrastructure.django.utils import close_django_connection
from eventsourcing.infrastructure.django.apps import DjangoConfig
from eventsourcing.infrastructure.django.factory import DjangoInfrastructureFactory
from eventsourcing.tests.sequenced_item_tests import base


class DjangoTestCase(TransactionTestCase):
    infrastructure_factory_class = DjangoInfrastructureFactory
    contiguous_record_ids = True

    def setUp(self):
        super(DjangoTestCase, self).setUp()
        # Setup tables (there isn't a Django datastore object, but we can do it like this).
        call_command('migrate', verbosity=0, interactive=False)
        sleep(1)

    def tearDown(self):
        # Drop tables (there isn't a Django datastore object, but we can do it like this).
        # call_command('migrate', 'django', 'zero', verbosity=0, interactive=False)
        super(DjangoTestCase, self).tearDown()

    def construct_datastore(self):
        pass

    def close_connections_before_forking(self):
        # If connection is already made close it.
        close_django_connection()


class TestDjangoRecordManagerWithIntegerSequences(DjangoTestCase, base.IntegerSequencedRecordTestCase):
    def construct_record_manager(self):
        return self.construct_entity_record_manager()


class TestDjangoRecordManagerWithoutContiguousRecordIDs(DjangoTestCase, base.IntegerSequencedRecordTestCase):
    contiguous_record_ids = False

    def construct_record_manager(self):
        return self.construct_entity_record_manager()


class TestDjangoRecordManagerWithTimestampSequences(DjangoTestCase, base.TimestampSequencedItemTestCase):
    def construct_record_manager(self):
        return self.construct_timestamp_sequenced_record_manager()


# class WithDjangoRecordManagers(DjangoTestCase, WithActiveRecordManagers):
#     def construct_entity_record_manager(self):
#         return construct_integer_sequenced_record_manager()
#
#     def construct_log_record_manager(self):
#         return construct_timestamp_sequenced_record_manager()
#
#     def construct_snapshot_record_manager(self):
#         return construct_snapshot_record_manager()
#

# class TestSimpleSequencedItemIteratorWithDjango(WithDjangoRecordManagers,
#                                                 SimpleSequencedItemteratorTestCase):
#     pass
#
#
# class TestThreadedSequencedItemIteratorWithDjango(WithDjangoRecordManagers,
#                                                   ThreadedSequencedItemIteratorTestCase):
#     pass

class TestConfigClass(unittest.TestCase):

    def test(self):
        self.assertEqual('eventsourcing.infrastructure.django', DjangoConfig.name)
