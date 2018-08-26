from eventsourcing.tests.example_application_tests import base
from eventsourcing.tests.sequenced_item_tests.test_sqlalchemy_record_manager import \
    SQLAlchemyRecordManagerTestCase


class TestExampleApplicationWithSQLAlchemy(SQLAlchemyRecordManagerTestCase, base.ExampleApplicationTestCase):
    pass
