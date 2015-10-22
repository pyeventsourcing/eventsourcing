import unittest

from eventsourcing.application.example_cassandra import ExampleApplicationWithCassandra
from eventsourcing.domain.model.example import Example
from eventsourcing.infrastructure.event_sourced_repos.example_repo import ExampleRepository


class TestCassandraApplication(unittest.TestCase):

    def test(self):
        # Setup the example application, use it as a context manager.
        with ExampleApplicationWithCassandra() as app:

            # Check there's an example repository.
            self.assertIsInstance(app.example_repo, ExampleRepository)

            assert isinstance(app, ExampleApplicationWithCassandra)  # For PyCharm...

            # Register a new example.
            example1 = app.register_new_example(a=10, b=20)

            self.assertIsInstance(example1, Example)

            # Check the example is available in the repo.
            entity1 = app.example_repo[example1.id]
            self.assertEqual(10, entity1.a)
            self.assertEqual(20, entity1.b)
            self.assertEqual(example1, entity1)

            # Change attribute values.
            entity1.a = 100

            # Check the new value is available in the repo.
            entity1 = app.example_repo[example1.id]
            self.assertEqual(100, entity1.a)

