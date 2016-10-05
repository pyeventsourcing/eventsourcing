from eventsourcing.application.example.with_sqlalchemy import ExampleApplicationWithSQLAlchemy
from eventsourcing.tests.example_application_testcase import ExampleApplicationTestCase


class TestApplicationWithSQLAlchemy(ExampleApplicationTestCase):

    def create_app(self):
        return ExampleApplicationWithSQLAlchemy(db_uri='sqlite:///:memory:')
