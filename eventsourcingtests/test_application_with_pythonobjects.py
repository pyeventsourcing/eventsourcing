from eventsourcing.application.example.with_pythonobjects import ExampleApplicationWithPythonObjects
from eventsourcingtests.example_application_testcase import ExampleApplicationTestCase


class TestApplicationWithPythonObjects(ExampleApplicationTestCase):

    def test_application_with_python_objects(self):
        # Setup the example application, use it as a context manager.
        with ExampleApplicationWithPythonObjects() as app:
            self.assert_is_example_application(app)
