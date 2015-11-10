from eventsourcing.application.example.with_cassandra import ExampleApplicationWithCassandra
from eventsourcingtests.example_application_testcase import ExampleApplicationTestCase


class TestApplicationWithCassandra(ExampleApplicationTestCase):

    def test_application_with_cassandra(self):
        # Setup the example application, use it as a context manager.
        with ExampleApplicationWithCassandra() as app:
            self.assert_is_example_application(app)

