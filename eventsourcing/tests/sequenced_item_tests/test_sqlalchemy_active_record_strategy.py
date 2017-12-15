from eventsourcing.infrastructure.sequenceditem import SequencedItem
from eventsourcing.infrastructure.sqlalchemy.models import IntegerSequencedRecord, SnapshotRecord, \
    TimestampSequencedRecord

from eventsourcing.infrastructure.sqlalchemy.strategy import SQLAlchemyRecordStrategy
from eventsourcing.tests.datastore_tests.test_sqlalchemy import SQLAlchemyDatastoreTestCase
from eventsourcing.tests.sequenced_item_tests.base import IntegerSequencedItemTestCase, \
    SimpleSequencedItemteratorTestCase, ThreadedSequencedItemIteratorTestCase, TimestampSequencedItemTestCase, \
    WithActiveRecordStrategies


def construct_integer_sequenced_active_record_strategy(datastore):
    return SQLAlchemyRecordStrategy(
        active_record_class=IntegerSequencedRecord,
        sequenced_item_class=SequencedItem,
        session=datastore.session,
    )


def construct_timestamp_sequenced_active_record_strategy(datastore):
    return SQLAlchemyRecordStrategy(
        active_record_class=TimestampSequencedRecord,
        sequenced_item_class=SequencedItem,
        session=datastore.session,
    )


def construct_snapshot_active_record_strategy(datastore):
    return SQLAlchemyRecordStrategy(
        active_record_class=SnapshotRecord,
        sequenced_item_class=SequencedItem,
        session=datastore.session,
    )


class TestSQLAlchemyRecordStrategyWithIntegerSequences(SQLAlchemyDatastoreTestCase,
                                                             IntegerSequencedItemTestCase):
    def construct_active_record_strategy(self):
        return construct_integer_sequenced_active_record_strategy(self.datastore)


class TestSQLAlchemyRecordStrategyWithTimestampSequences(SQLAlchemyDatastoreTestCase,
                                                               TimestampSequencedItemTestCase):
    def construct_active_record_strategy(self):
        return construct_timestamp_sequenced_active_record_strategy(self.datastore)


class WithSQLAlchemyRecordStrategies(WithActiveRecordStrategies, SQLAlchemyDatastoreTestCase):
    def construct_entity_active_record_strategy(self):
        return construct_integer_sequenced_active_record_strategy(self.datastore)

    def construct_log_active_record_strategy(self):
        return construct_timestamp_sequenced_active_record_strategy(self.datastore)

    def construct_snapshot_active_record_strategy(self):
        return construct_snapshot_active_record_strategy(self.datastore)


class TestSimpleIteratorWithSQLAlchemy(WithSQLAlchemyRecordStrategies,
                                       SimpleSequencedItemteratorTestCase):
    pass


class TestThreadedIteratorWithSQLAlchemy(WithSQLAlchemyRecordStrategies,
                                         ThreadedSequencedItemIteratorTestCase):
    use_named_temporary_file = True
