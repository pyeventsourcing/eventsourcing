import os
import unittest

import django
from django.core.management import call_command

from eventsourcing.infrastructure.django.apps import DjangoConfig

os.environ['DJANGO_SETTINGS_MODULE'] = 'eventsourcing.tests.djangoproject.djangoproject.settings'
django.setup()

from django.test import TransactionTestCase

from eventsourcing.infrastructure.django.manager import DjangoRecordManager

from eventsourcing.infrastructure.django.models import IntegerSequencedRecord, SnapshotRecord, \
    TimestampSequencedRecord
from eventsourcing.infrastructure.sequenceditem import SequencedItem
from eventsourcing.tests.sequenced_item_tests.base import IntegerSequencedItemTestCase, TimestampSequencedItemTestCase


class InfrastructureFactory(object):

    def __init__(self, record_strategy_class, convert_position_float_to_decimal=False):
        self.record_strategy_class = record_strategy_class
        self.convert_position_float_to_decimal = convert_position_float_to_decimal

    def construct_integer_sequenced_record_manager(self):
        return self.construct_record_strategy(
            record_class=IntegerSequencedRecord,
            sequenced_item_class=SequencedItem
        )

    def construct_snapshot_record_manager(self):
        return self.construct_record_strategy(
            record_class=SnapshotRecord,
            sequenced_item_class=SequencedItem
        )

    def construct_record_strategy(self, record_class, sequenced_item_class):
        return self.record_strategy_class(
            record_class=record_class,
            sequenced_item_class=sequenced_item_class,
        )

    def construct_timestamp_sequenced_record_manager(self):
        return self.record_strategy_class(
            record_class=TimestampSequencedRecord,
            sequenced_item_class=SequencedItem,
            convert_position_float_to_decimal=self.convert_position_float_to_decimal
        )


class DjangoTestCase(TransactionTestCase):
    cancel_sqlite3_decimal_converter = False

    def setUp(self):
        super(DjangoTestCase, self).setUp()
        call_command('migrate')
        self.factory = InfrastructureFactory(
            record_strategy_class=DjangoRecordManager,
            convert_position_float_to_decimal=self.cancel_sqlite3_decimal_converter
        )

    def construct_entity_record_manager(self):
        return self.factory.construct_integer_sequenced_record_manager()

    def construct_snapshot_record_manager(self):
        return self.factory.construct_snapshot_record_manager()

    def construct_timestamp_sequenced_record_manager(self):
        return self.factory.construct_timestamp_sequenced_record_manager()


# @skipIf(six.PY2, 'Django 2.0 does not support Python 2.7')  # using 1.11
class TestDjangoRecordManagerWithIntegerSequences(DjangoTestCase, IntegerSequencedItemTestCase):
    def construct_record_manager(self):
        return self.factory.construct_integer_sequenced_record_manager()


class TestDjangoRecordManagerWithTimestampSequences(DjangoTestCase, TimestampSequencedItemTestCase):
    cancel_sqlite3_decimal_converter = True

    def construct_record_manager(self):
        return self.factory.construct_timestamp_sequenced_record_manager()


# def construct_timestamp_sequenced_record_manager():
#     return DjangoRecordManager(
#         record_class=TimestampSequencedRecord,
#         sequenced_item_class=SequencedItem,
#     )
#
#
# def construct_snapshot_record_manager():
#     return DjangoRecordManager(
#         record_class=SnapshotRecord,
#         sequenced_item_class=SequencedItem,
#     )
#


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
