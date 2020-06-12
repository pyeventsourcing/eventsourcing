from eventsourcing.tests.example_application_tests import base
from eventsourcing.tests.sequenced_item_tests.test_dynamodb_record_manager import (
    WithDynamoDbRecordManagers,
)


class TestExampleApplicationWithDynamoDb(
    WithDynamoDbRecordManagers, base.ExampleApplicationTestCase
):
    pass
