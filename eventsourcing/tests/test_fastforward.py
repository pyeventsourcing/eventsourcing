from eventsourcing.application.example.base import ExampleApplication
from eventsourcing.application.example.with_cassandra import ExampleApplicationWithCassandra
from eventsourcing.application.example.with_pythonobjects import ExampleApplicationWithPythonObjects
from eventsourcing.domain.model.example import Example
from eventsourcing.exceptions import ConcurrencyError
from eventsourcing.tests.unit_test_cases_cassandra import CassandraTestCase
from eventsourcing.tests.unit_test_cases_example_application import ExampleApplicationTestCase


class TestFastForward(CassandraTestCase, ExampleApplicationTestCase):
    def create_app(self):
        return ExampleApplicationWithCassandra()
        # return ExampleApplicationWithPythonObjects()

    def test(self):
        assert isinstance(self.app, ExampleApplication)
        example = self.app.register_new_example(1, 2)
        instance1 = self.app.example_repo[example.id]
        instance2 = self.app.example_repo[example.id]

        assert isinstance(instance1, Example)
        assert isinstance(instance2, Example)

        self.assertEqual(instance1.version, 1)
        self.assertEqual(instance2.version, 1)

        # Evolve instance1 by two versions.
        instance1.beat_heart()
        # instance1.beat_heart()
        self.assertEqual(instance1.version, 2)

        # Try to evolve instance2 from the same version.
        # - check it raises a concurrency error
        preop_state = instance2.__dict__.copy()
        with self.assertRaises(ConcurrencyError):
            instance2.beat_heart()

        # Reset instance2 to its pre-op state.
        instance2.__dict__.update(preop_state)
        self.assertEqual(instance2.version, 1)

        # Fast forward instance2 from pre-op state.
        instance3 = self.app.example_repo.fastforward(instance2)
        self.assertEqual(instance2.version, 1)
        self.assertEqual(instance3.version, 2)

        # Try again to beat heart.
        instance3.beat_heart()
        self.assertEqual(instance3.version, 3)

        # Try to evolve instance1 from its stale version.
        preop_state = instance1.__dict__.copy()
        with self.assertRaises(ConcurrencyError):
            instance1.beat_heart()

        # Reset instance1 to pre-op state.
        instance1.__dict__.update(preop_state)

        # Fast forward instance1 from pre-op state.
        instance4 = self.app.example_repo.fastforward(instance1)
        self.assertEqual(instance1.version, 2)
        self.assertEqual(instance4.version, 3)

        # Try again to beat heart.
        instance4.beat_heart()
        self.assertEqual(instance4.version, 4)
