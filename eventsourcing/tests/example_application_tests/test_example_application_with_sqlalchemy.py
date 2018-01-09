from eventsourcing.tests.example_application_tests.base import ExampleApplicationTestCase
from eventsourcing.tests.sequenced_item_tests.test_sqlalchemy_record_manager import \
    WithSQLAlchemyRecordManagers


class TestExampleApplicationWithSQLAlchemy(WithSQLAlchemyRecordManagers, ExampleApplicationTestCase):
    pass
