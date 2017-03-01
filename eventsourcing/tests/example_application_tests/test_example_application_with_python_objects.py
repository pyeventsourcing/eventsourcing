from eventsourcing.application.example.with_pythonobjects import ExampleApplicationWithPythonObjects
from eventsourcing.tests.unit_test_cases_example_application import ExampleApplicationTestCase


class TestApplicationWithPythonObjects(ExampleApplicationTestCase):

    def create_app(self):
        return ExampleApplicationWithPythonObjects()
