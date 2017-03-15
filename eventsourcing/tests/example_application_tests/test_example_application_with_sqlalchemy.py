from eventsourcing.tests.example_application_tests.base import ExampleApplicationTestCase
from eventsourcing.tests.sequenced_item_tests.test_sqlalchemy_sequence_repository import \
    SQLAlchemyRepoTestCase


class TestExampleApplicationWithSQLAlchemy(SQLAlchemyRepoTestCase, ExampleApplicationTestCase):
    pass
