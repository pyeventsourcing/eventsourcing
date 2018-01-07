import os
import unittest

import django
from django.core.management import call_command

from eventsourcing.infrastructure.django.apps import DjangoConfig

os.environ['DJANGO_SETTINGS_MODULE'] = 'eventsourcing.tests.djangoproject.djangoproject.settings'
django.setup()

from django.test import TransactionTestCase

from eventsourcing.infrastructure.django.strategy import DjangoRecordStrategy

from eventsourcing.infrastructure.django.models import IntegerSequencedRecord, SnapshotRecord, \
    TimestampSequencedRecord
from eventsourcing.infrastructure.sequenceditem import SequencedItem
from eventsourcing.tests.sequenced_item_tests.base import IntegerSequencedItemTestCase, TimestampSequencedItemTestCase


class InfrastructureFactory(object):

    def __init__(self, record_strategy_class, cancel_sqlite3_decimal_converter=False):
        self.record_strategy_class = record_strategy_class
        self.cancel_sqlite3_decimal_converter = cancel_sqlite3_decimal_converter

    def construct_integer_sequenced_active_record_strategy(self):
        return self.construct_record_strategy(
            active_record_class=IntegerSequencedRecord,
            sequenced_item_class=SequencedItem
        )

    def construct_snapshot_active_record_strategy(self):
        return self.construct_record_strategy(
            active_record_class=SnapshotRecord,
            sequenced_item_class=SequencedItem
        )

    def construct_record_strategy(self, active_record_class, sequenced_item_class):
        return self.record_strategy_class(
            active_record_class=active_record_class,
            sequenced_item_class=sequenced_item_class,
        )

    def construct_timestamp_sequenced_active_record_strategy(self):
        return self.record_strategy_class(
            active_record_class=TimestampSequencedRecord,
            sequenced_item_class=SequencedItem,
            convert_position_float_to_decimal=self.cancel_sqlite3_decimal_converter
        )


class DjangoTestCase(TransactionTestCase):
    cancel_sqlite3_decimal_converter = False

    def setUp(self):
        super(DjangoTestCase, self).setUp()
        call_command('migrate')
        self.factory = InfrastructureFactory(
            record_strategy_class=DjangoRecordStrategy,
            cancel_sqlite3_decimal_converter=self.cancel_sqlite3_decimal_converter
        )

    def construct_entity_active_record_strategy(self):
        return self.factory.construct_integer_sequenced_active_record_strategy()

    def construct_snapshot_active_record_strategy(self):
        return self.factory.construct_snapshot_active_record_strategy()

    def construct_timestamp_sequenced_active_record_strategy(self):
        return self.factory.construct_timestamp_sequenced_active_record_strategy()


# @skipIf(six.PY2, 'Django 2.0 does not support Python 2.7')  # using 1.11
class TestDjangoRecordStrategyWithIntegerSequences(DjangoTestCase, IntegerSequencedItemTestCase):
    def construct_active_record_strategy(self):
        return self.factory.construct_integer_sequenced_active_record_strategy()


class TestDjangoRecordStrategyWithTimestampSequences(DjangoTestCase, TimestampSequencedItemTestCase):
    cancel_sqlite3_decimal_converter = True

    def construct_active_record_strategy(self):
        return self.factory.construct_timestamp_sequenced_active_record_strategy()


# def construct_timestamp_sequenced_active_record_strategy():
#     return DjangoRecordStrategy(
#         active_record_class=TimestampSequencedRecord,
#         sequenced_item_class=SequencedItem,
#     )
#
#
# def construct_snapshot_active_record_strategy():
#     return DjangoRecordStrategy(
#         active_record_class=SnapshotRecord,
#         sequenced_item_class=SequencedItem,
#     )
#


# class WithDjangoRecordStrategies(DjangoTestCase, WithActiveRecordStrategies):
#     def construct_entity_active_record_strategy(self):
#         return construct_integer_sequenced_active_record_strategy()
#
#     def construct_log_active_record_strategy(self):
#         return construct_timestamp_sequenced_active_record_strategy()
#
#     def construct_snapshot_active_record_strategy(self):
#         return construct_snapshot_active_record_strategy()
#

# class TestSimpleSequencedItemIteratorWithDjango(WithDjangoRecordStrategies,
#                                                 SimpleSequencedItemteratorTestCase):
#     pass
#
#
# class TestThreadedSequencedItemIteratorWithDjango(WithDjangoRecordStrategies,
#                                                   ThreadedSequencedItemIteratorTestCase):
#     pass

class TestConfigClass(unittest.TestCase):

    def test(self):
        self.assertEqual('eventsourcing.infrastructure.django', DjangoConfig.name)
