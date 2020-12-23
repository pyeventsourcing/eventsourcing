from eventsourcing.infrastructure.sqlalchemy.records import StoredEventRecord
from eventsourcing.tests.datastore_tests import test_sqlalchemy
from eventsourcing.tests.sequenced_item_tests import base


class SQLAlchemyRecordManagerTestCase(
    test_sqlalchemy.SQLAlchemyDatastoreTestCase, base.WithRecordManagers
):
    """
    Base class for test cases that need record manager with SQLAlchemy.
    """


class TestSQLAlchemyRecordManagerWithTimestampSequencedItems(
    SQLAlchemyRecordManagerTestCase, base.TimestampSequencedItemTestCase
):
    """
    Test case for timestamp sequenced record manager with SQLAlchemy.
    """

class TestSQLAlchemyRecordManagerNotifications(
    SQLAlchemyRecordManagerTestCase, base.RecordManagerNotificationsTestCase
):
    pass

class TestSQLAlchemyRecordManagerTrackingRecords(
    SQLAlchemyRecordManagerTestCase, base.RecordManagerTrackingRecordsTestCase
):
    pass

class TestSQLAlchemyRecordManagerWithIntegerSequencedItems(
    SQLAlchemyRecordManagerTestCase, base.IntegerSequencedRecordTestCase
):
    pass

class TestSQLAlchemyRecordManagerWithStoredEvents(
    SQLAlchemyRecordManagerTestCase, base.RecordManagerStoredEventsTestCase
):
    def create_factory_kwargs(self):
        kwargs = super().create_factory_kwargs()
        kwargs['integer_sequenced_record_class'] = StoredEventRecord
        return kwargs




class TestSimpleIteratorWithSQLAlchemy(
    SQLAlchemyRecordManagerTestCase, base.SequencedItemIteratorTestCase
):
    """
    Test case for simple iterator in record manager with SQLAlchemy.
    """


class TestThreadedIteratorWithSQLAlchemy(
    SQLAlchemyRecordManagerTestCase, base.ThreadedSequencedItemIteratorTestCase
):
    """
    Test case for threaded iterator in record manager with SQLAlchemy.
    """

    use_named_temporary_file = True
