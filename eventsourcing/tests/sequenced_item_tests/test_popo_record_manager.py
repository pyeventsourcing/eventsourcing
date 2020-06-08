from eventsourcing.infrastructure.popo.factory import PopoInfrastructureFactory
from eventsourcing.infrastructure.popo.mapper import SequencedItemMapperForPopo
from eventsourcing.infrastructure.popo.records import StoredEventRecord
from eventsourcing.tests.sequenced_item_tests import base


class PopoTestCase(object):
    infrastructure_factory_class = PopoInfrastructureFactory
    sequenced_item_mapper_class = SequencedItemMapperForPopo

    contiguous_record_ids = True

    def construct_datastore(self):
        pass


class TestPopoRecordManagerWithIntegerSequences(
    PopoTestCase, base.IntegerSequencedRecordTestCase
):
    def create_factory_kwargs(self):
        kwargs = super().create_factory_kwargs()
        kwargs['integer_sequenced_record_class'] = StoredEventRecord
        kwargs['application_name'] = 'app'
        return kwargs


class TestPopoRecordManagerNotifications(
    PopoTestCase, base.RecordManagerNotificationsTestCase
):
    def create_factory_kwargs(self):
        kwargs = super().create_factory_kwargs()
        kwargs['integer_sequenced_record_class'] = StoredEventRecord
        kwargs['application_name'] = 'app'
        return kwargs


class TestPopoRecordManagerTracking(
    PopoTestCase, base.RecordManagerTrackingRecordsTestCase
):
    def create_factory_kwargs(self):
        kwargs = super().create_factory_kwargs()
        kwargs['integer_sequenced_record_class'] = StoredEventRecord
        return kwargs


class TestPopoRecordManagerWithStoredEvents(
    PopoTestCase, base.RecordManagerStoredEventsTestCase
):
    def create_factory_kwargs(self):
        kwargs = super().create_factory_kwargs()
        kwargs['integer_sequenced_record_class'] = StoredEventRecord
        return kwargs


#
# class TestPopoRecordManagerWithTimestampSequences(PopoTestCase, base.TimestampSequencedItemTestCase):
#     def construct_record_manager(self):
#         return self.construct_timestamp_sequenced_record_manager()
#

# class WithPopoRecordManagers(PopoTestCase, WithActiveRecordManagers):
#     def construct_entity_record_manager(self):
#         return construct_integer_sequenced_record_manager()
#
#     def construct_log_record_manager(self):
#         return construct_timestamp_sequenced_record_manager()
#
#     def construct_snapshot_record_manager(self):
#         return construct_snapshot_record_manager()
#

# class TestSimpleSequencedItemIteratorWithPopo(WithPopoRecordManagers,
#                                                 SimpleSequencedItemteratorTestCase):
#     pass
#
#
# class TestThreadedSequencedItemIteratorWithPopo(WithPopoRecordManagers,
#                                                   ThreadedSequencedItemIteratorTestCase):
#     pass
