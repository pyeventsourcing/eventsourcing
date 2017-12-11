import os

from django.core.management import call_command

os.environ['DJANGO_SETTINGS_MODULE'] = 'eventsourcing.tests.djangoproject.djangoproject.settings'

import django
django.setup()

from django.test import TestCase


from eventsourcing.infrastructure.django.activerecords import DjangoActiveRecordStrategy

from eventsourcing.infrastructure.django.models import  IntegerSequencedItemRecord, SnapshotRecord, \
    TimestampSequencedItemRecord
from eventsourcing.infrastructure.sequenceditem import SequencedItem
from eventsourcing.tests.sequenced_item_tests.base import IntegerSequencedItemTestCase


class DjangoTestCase(TestCase):

    def setUp(self):
        super(DjangoTestCase, self).setUp()
        call_command('migrate')


class TestDjangoActiveRecordStrategyWithIntegerSequences(DjangoTestCase, IntegerSequencedItemTestCase):
    def construct_active_record_strategy(self):
        return construct_integer_sequenced_active_record_strategy()


def construct_integer_sequenced_active_record_strategy():
    return DjangoActiveRecordStrategy(
        active_record_class=IntegerSequencedItemRecord,
        sequenced_item_class=SequencedItem,
    )


# def construct_timestamp_sequenced_active_record_strategy():
#     return DjangoActiveRecordStrategy(
#         active_record_class=TimestampSequencedItemRecord,
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

# class TestDjangoActiveRecordStrategyWithTimestampSequences(DjangoDatastoreTestCase,
#                                                            TimestampSequencedItemTestCase):
#     def construct_active_record_strategy(self):
#         return construct_timestamp_sequenced_active_record_strategy()


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
