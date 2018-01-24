import os
import unittest

import django
os.environ['DJANGO_SETTINGS_MODULE'] = 'eventsourcing.tests.djangoproject.djangoproject.settings'
django.setup()

from django.core.management import call_command

from eventsourcing.infrastructure.django.apps import DjangoConfig
from eventsourcing.infrastructure.django.factory import DjangoInfrastructureFactory

from django.test import TransactionTestCase

from eventsourcing.tests.sequenced_item_tests.base import IntegerSequencedRecordTestCase, TimestampSequencedItemTestCase


class DjangoTestCase(TransactionTestCase):

    infrastructure_factory_class = DjangoInfrastructureFactory
    contiguous_record_ids = True

    def setUp(self):
        super(DjangoTestCase, self).setUp()
        call_command('migrate')


# @skipIf(six.PY2, 'Django 2.0 does not support Python 2.7')  # using 1.11
class TestDjangoRecordManagerWithIntegerSequences(DjangoTestCase, IntegerSequencedRecordTestCase):
    def construct_record_manager(self):
        return self.construct_entity_record_manager()

class TestDjangoRecordManagerWithoutContiguousRecordIDs(DjangoTestCase, IntegerSequencedRecordTestCase):
    contiguous_record_ids = False
    def construct_record_manager(self):
        return self.construct_entity_record_manager()


class TestDjangoRecordManagerWithTimestampSequences(DjangoTestCase, TimestampSequencedItemTestCase):
    cancel_sqlite3_decimal_converter = True

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
