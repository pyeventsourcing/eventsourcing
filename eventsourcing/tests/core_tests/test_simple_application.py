from eventsourcing.application.simple import SimpleApplication, SnapshottingApplication
from eventsourcing.domain.model.events import assert_event_handlers_empty
from eventsourcing.interface.notificationlog import NotificationLogReader
from eventsourcing.tests.core_tests.test_aggregate_root import ExampleAggregateRoot
from eventsourcing.tests.datastore_tests.test_sqlalchemy import SQLAlchemyDatastoreTestCase
from eventsourcing.utils.random import encode_random_bytes


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

            # Check the notifications.
            reader = NotificationLogReader(app.notification_log)
            notifications = reader.read()
            self.assertEqual(1, len(notifications))
            topic = 'eventsourcing.tests.core_tests.test_aggregate_root#ExampleAggregateRoot.Created'
            self.assertEqual(topic, notifications[0]['topic'])

    def get_application(self):
        return SimpleApplication(cipher_key=encode_random_bytes(16))


class TestSnapshottingApplication(TestSimpleApplication):
    def get_application(self):
        return SnapshottingApplication()
