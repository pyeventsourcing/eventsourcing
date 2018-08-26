from eventsourcing.tests.datastore_tests import test_sqlalchemy
from eventsourcing.tests.sequenced_item_tests import base


class SQLAlchemyRecordManagerTestCase(test_sqlalchemy.SQLAlchemyDatastoreTestCase,
                                      base.WithRecordManagers):
    """
    Base class for test cases that need record manager with SQLAlchemy.
    """


class TestSQLAlchemyRecordManagerWithIntegerSequences(SQLAlchemyRecordManagerTestCase,
                                                      base.IntegerSequencedRecordTestCase):
    """
    Test case for integer sequenced record manager with SQLAlchemy.
    """


class TestSQLAlchemyRecordManagerWithTimestampSequences(SQLAlchemyRecordManagerTestCase,
                                                        base.TimestampSequencedItemTestCase):
    """
    Test case for timestamp sequenced record manager with SQLAlchemy.
    """


class TestSimpleIteratorWithSQLAlchemy(SQLAlchemyRecordManagerTestCase,
                                       base.SequencedItemIteratorTestCase):
    """
    Test case for simple iterator in record manager with SQLAlchemy.
    """


class TestThreadedIteratorWithSQLAlchemy(SQLAlchemyRecordManagerTestCase,
                                         base.ThreadedSequencedItemIteratorTestCase):
    """
    Test case for threaded iterator in record manager with SQLAlchemy.
    """
    use_named_temporary_file = True
