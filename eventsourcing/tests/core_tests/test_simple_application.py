from eventsourcing.application.simple import SimpleApplication, SnapshottingApplication
from eventsourcing.domain.model.events import assert_event_handlers_empty
from eventsourcing.tests.core_tests.test_aggregate_root import ExampleAggregateRoot
from eventsourcing.tests.datastore_tests.test_sqlalchemy import SQLAlchemyDatastoreTestCase


class TestSimpleApplication(SQLAlchemyDatastoreTestCase):
    def tearDown(self):
        # Check the close() method leaves everything unsubscribed.
        assert_event_handlers_empty()

    def test(self):
        with self.get_application() as app:
            # Check the application's persistence policy,
            # repository, and event store, are working.
            aggregate = ExampleAggregateRoot.__create__()
            aggregate.__save__()
            self.assertTrue(aggregate.id in app.repository)

    def get_application(self):
        return SimpleApplication()


class TestSnapshottingApplication(TestSimpleApplication):
    def get_application(self):
        return SnapshottingApplication()
