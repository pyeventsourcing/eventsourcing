import os
import unittest

import django
from django.core.management import call_command

from eventsourcing.infrastructure.django.apps import DjangoConfig

os.environ['DJANGO_SETTINGS_MODULE'] = 'eventsourcing.tests.djangoproject.djangoproject.settings'
django.setup()

from django.test import TransactionTestCase

from eventsourcing.infrastructure.django.strategy import DjangoActiveRecordStrategy

from eventsourcing.infrastructure.django.models import IntegerSequencedRecord, SnapshotRecord, \
    TimestampSequencedRecord
from eventsourcing.infrastructure.sequenceditem import SequencedItem
from eventsourcing.tests.sequenced_item_tests.base import IntegerSequencedItemTestCase, TimestampSequencedItemTestCase


class DjangoTestCase(TransactionTestCase):
    cancel_sqlite3_decimal_converter = False

    def setUp(self):
        super(DjangoTestCase, self).setUp()
        call_command('migrate')

    def construct_entity_active_record_strategy(self):
        return self.construct_integer_sequenced_active_record_strategy()

    def construct_snapshot_active_record_strategy(self):
        return DjangoActiveRecordStrategy(
            active_record_class=SnapshotRecord,
            sequenced_item_class=SequencedItem,
        )

    def construct_integer_sequenced_active_record_strategy(self):
        return DjangoActiveRecordStrategy(
            active_record_class=IntegerSequencedRecord,
            sequenced_item_class=SequencedItem,
        )

    def construct_timestamp_sequenced_active_record_strategy(self):
        return DjangoActiveRecordStrategy(
            active_record_class=TimestampSequencedRecord,
            sequenced_item_class=SequencedItem,
            convert_position_float_to_decimal=self.cancel_sqlite3_decimal_converter
        )


# @skipIf(six.PY2, 'Django 2.0 does not support Python 2.7')  # using 1.11
class TestDjangoActiveRecordStrategyWithIntegerSequences(DjangoTestCase, IntegerSequencedItemTestCase):
    def construct_active_record_strategy(self):
        return self.construct_integer_sequenced_active_record_strategy()


class TestDjangoActiveRecordStrategyWithTimestampSequences(DjangoTestCase, TimestampSequencedItemTestCase):
    cancel_sqlite3_decimal_converter = True

    def construct_active_record_strategy(self):
        return self.construct_timestamp_sequenced_active_record_strategy()


# def construct_timestamp_sequenced_active_record_strategy():
#     return DjangoActiveRecordStrategy(
#         active_record_class=TimestampSequencedRecord,
#         sequenced_item_class=SequencedItem,
#     )
#
#
# def construct_snapshot_active_record_strategy():
#     return DjangoActiveRecordStrategy(
#         active_record_class=SnapshotRecord,
#         sequenced_item_class=SequencedItem,
#     )
#


# class WithDjangoActiveRecordStrategies(DjangoTestCase, WithActiveRecordStrategies):
#     def construct_entity_active_record_strategy(self):
#         return construct_integer_sequenced_active_record_strategy()
#
#     def construct_log_active_record_strategy(self):
#         return construct_timestamp_sequenced_active_record_strategy()
#
#     def construct_snapshot_active_record_strategy(self):
#         return construct_snapshot_active_record_strategy()
#

# class TestSimpleSequencedItemIteratorWithDjango(WithDjangoActiveRecordStrategies,
#                                                 SimpleSequencedItemteratorTestCase):
#     pass
#
#
# class TestThreadedSequencedItemIteratorWithDjango(WithDjangoActiveRecordStrategies,
#                                                   ThreadedSequencedItemIteratorTestCase):
#     pass

class TestConfigClass(unittest.TestCase):

    def test(self):
        self.assertEqual('eventsourcing.infrastructure.django', DjangoConfig.name)
