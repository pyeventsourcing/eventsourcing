from eventsourcing.application.example.with_sqlalchemy import ExampleApplicationWithSQLAlchemy
from eventsourcing.tests.unit_test_cases_example_application import ExampleApplicationTestCase


class TestApplicationWithSQLAlchemy(ExampleApplicationTestCase):

    def create_app(self):
        return ExampleApplicationWithSQLAlchemy(db_uri='sqlite:///:memory:')
