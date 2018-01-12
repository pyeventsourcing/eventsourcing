from eventsourcing.infrastructure.sequenceditem import SequencedItem
from eventsourcing.infrastructure.sqlalchemy.manager import SQLAlchemyRecordManager
from eventsourcing.infrastructure.sqlalchemy.records import IntegerSequencedRecord, SnapshotRecord, \
    TimestampSequencedRecord
from eventsourcing.tests.datastore_tests.test_sqlalchemy import SQLAlchemyDatastoreTestCase
from eventsourcing.tests.sequenced_item_tests.base import IntegerSequencedItemTestCase, \
    SimpleSequencedItemteratorTestCase, ThreadedSequencedItemIteratorTestCase, TimestampSequencedItemTestCase, \
    WithActiveRecordManagers


# Todo: Change this use InfrastructureFactory.
def construct_integer_sequenced_record_manager(datastore):
    return SQLAlchemyRecordManager(
        record_class=IntegerSequencedRecord,
        sequenced_item_class=SequencedItem,
        session=datastore.session,
        contiguous_record_ids=True,
    )


def construct_timestamp_sequenced_record_manager(datastore):
    return SQLAlchemyRecordManager(
        record_class=TimestampSequencedRecord,
        sequenced_item_class=SequencedItem,
        session=datastore.session,
        contiguous_record_ids=True,
    )


def construct_snapshot_record_manager(datastore):
    return SQLAlchemyRecordManager(
        record_class=SnapshotRecord,
        sequenced_item_class=SequencedItem,
        session=datastore.session,
    )


class TestSQLAlchemyRecordManagerWithIntegerSequences(SQLAlchemyDatastoreTestCase,
                                                      IntegerSequencedItemTestCase):
    def construct_record_manager(self):
        return construct_integer_sequenced_record_manager(self.datastore)


class TestSQLAlchemyRecordManagerWithTimestampSequences(SQLAlchemyDatastoreTestCase,
                                                        TimestampSequencedItemTestCase):
    def construct_record_manager(self):
        return construct_timestamp_sequenced_record_manager(self.datastore)


class WithSQLAlchemyRecordManagers(WithActiveRecordManagers, SQLAlchemyDatastoreTestCase):
    def construct_entity_record_manager(self):
        return construct_integer_sequenced_record_manager(self.datastore)

    def construct_log_record_manager(self):
        return construct_timestamp_sequenced_record_manager(self.datastore)

    def construct_snapshot_record_manager(self):
        return construct_snapshot_record_manager(self.datastore)


class TestSimpleIteratorWithSQLAlchemy(WithSQLAlchemyRecordManagers,
                                       SimpleSequencedItemteratorTestCase):
    pass


class TestThreadedIteratorWithSQLAlchemy(WithSQLAlchemyRecordManagers,
                                         ThreadedSequencedItemIteratorTestCase):
    use_named_temporary_file = True
