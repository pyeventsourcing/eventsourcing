from eventsourcing.application.example.with_pythonobjects import ExampleApplicationWithPythonObjects
from eventsourcingtests.example_application_testcase import ExampleApplicationTestCase


class TestApplicationWithPythonObjects(ExampleApplicationTestCase):

    def create_app(self):
        return ExampleApplicationWithPythonObjects()
