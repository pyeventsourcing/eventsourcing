from eventsourcing.tests.example_application_tests.base import ExampleApplicationTestCase
from eventsourcing.tests.sequenced_item_tests.test_sqlalchemy_active_record_strategy import \
    WithSQLAlchemyRecordStrategies


class TestExampleApplicationWithSQLAlchemy(WithSQLAlchemyRecordStrategies, ExampleApplicationTestCase):
    pass
