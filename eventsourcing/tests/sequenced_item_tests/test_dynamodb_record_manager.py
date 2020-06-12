from eventsourcing.tests.datastore_tests.test_dynamodb import (
    DynamoDbDatastoreTestCase,
)
from eventsourcing.tests.sequenced_item_tests import base


class TestDynamoDbRecordManagerWithIntegerSequences(
    DynamoDbDatastoreTestCase, base.IntegerSequencedRecordTestCase
):
    pass


class TestDynamoDbRecordManagerWithTimestampSequences(
    DynamoDbDatastoreTestCase, base.TimestampSequencedItemTestCase
):
    pass


class WithDynamoDbRecordManagers(DynamoDbDatastoreTestCase, base.WithRecordManagers):
    pass


class TestSequencedItemIteratorWithDynamoDb(
    WithDynamoDbRecordManagers, base.SequencedItemIteratorTestCase
):
    pass


class TestThreadedSequencedItemIteratorWithDynamoDb(
    WithDynamoDbRecordManagers, base.ThreadedSequencedItemIteratorTestCase
):
    pass
