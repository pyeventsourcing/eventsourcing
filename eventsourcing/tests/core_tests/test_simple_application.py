from unittest import TestCase

from eventsourcing.tests.sequenced_item_tests.test_django_record_manager import DjangoTestCase

from eventsourcing.application.django import ApplicationWithDjango
from eventsourcing.application.sqlalchemy import SimpleApplication, ApplicationWithSnapshotting
from eventsourcing.domain.model.events import assert_event_handlers_empty, DomainEvent
from eventsourcing.interface.notificationlog import NotificationLogReader
from eventsourcing.tests.core_tests.test_aggregate_root import ExampleAggregateRoot
from eventsourcing.utils.random import encode_random_bytes


class TestSimpleApplication(TestCase):

    application_class = SimpleApplication

    def test(self):
        with self.get_application() as app:

            # Start with a new table.
            app.drop_table()
            app.drop_table()
            app.setup_table()
            app.setup_table()

            # Check the application's persistence policy,
            # repository, and event store, are working.
            aggregate = ExampleAggregateRoot.__create__()
            aggregate.__save__()
            self.assertTrue(aggregate.id in app.repository)

            # Check the notifications.
            reader = NotificationLogReader(app.notification_log)
            notifications = reader.read_list()
            self.assertEqual(1, len(notifications))
            topic = 'eventsourcing.tests.core_tests.test_aggregate_root#ExampleAggregateRoot.Created'
            self.assertEqual(topic, notifications[0]['event_type'])

            app.drop_table()

    def get_application(self):
        return self.application_class(
            cipher_key=encode_random_bytes(16),
            persist_event_type=DomainEvent,

        )

    def tearDown(self):
        # Check the close() method leaves everything unsubscribed.
        assert_event_handlers_empty()


class TestSimpleApplicationWithDjango(DjangoTestCase, TestSimpleApplication):
    application_class = ApplicationWithDjango


class TestSnapshottingApplication(TestSimpleApplication):
    application_class = ApplicationWithSnapshotting
