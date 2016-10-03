import eventsourcingtests.test_application_with_pythonobjects as testcase
from eventsourcing.application.example.base import ExampleApplication
from eventsourcing.application.example.with_pythonobjects import ExampleApplicationWithPythonObjects
from eventsourcing.domain.model.example import Example
from eventsourcing.exceptions import ConcurrencyError


class TestOptimisticConcurrencyControl(testcase.TestApplicationWithPythonObjects):

    def create_app(self):
        return ExampleApplicationWithPythonObjects()

    def test(self):
        assert isinstance(self.app, ExampleApplication)
        example = self.app.register_new_example(1, 2)
        instance1 = self.app.example_repo[example.id]
        instance2 = self.app.example_repo[example.id]

        assert isinstance(instance1, Example)
        assert isinstance(instance2, Example)
        instance1.beat_heart()
        with self.assertRaises(ConcurrencyError):
            instance2.beat_heart()
