from eventsourcing.tests.example_application_tests.base import ExampleApplicationTestCase
from eventsourcing.tests.sequenced_item_repository_tests.test_sqlalchemy_stored_event_repository import \
    SQLAlchemyRepoTestCase


class TestExampleApplicationWithSQLAlchemy(SQLAlchemyRepoTestCase, ExampleApplicationTestCase):
    pass
