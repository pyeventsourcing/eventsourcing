from unittest import TestCase

from eventsourcing.application.axon import AxonApplication
from eventsourcing.application.django import DjangoApplication
from eventsourcing.application.notificationlog import NotificationLogReader
from eventsourcing.application.popo import PopoApplication
from eventsourcing.application.simple import SimpleApplication
from eventsourcing.application.snapshotting import SnapshottingApplication
from eventsourcing.application.sqlalchemy import SQLAlchemyApplication
from eventsourcing.domain.model.events import DomainEvent, assert_event_handlers_empty
from eventsourcing.exceptions import ProgrammingError
from eventsourcing.tests.core_tests.test_aggregate_root import ExampleAggregateRoot
from eventsourcing.tests.sequenced_item_tests.test_django_record_manager import (
    DjangoTestCase,
)
from eventsourcing.utils.random import encoded_random_bytes


class TestSimpleApplication(TestCase):

    application_class = SimpleApplication
    infrastructure_class = SQLAlchemyApplication

    def test_simple_application_without_infrastructure(self):
        with self.application_class() as app:

            with self.assertRaises(ProgrammingError):
                app.datastore

            with self.assertRaises(ProgrammingError):
                app.repository

            with self.assertRaises(ProgrammingError):
                app.event_store

            with self.assertRaises(ProgrammingError):
                app.notification_log

            with self.assertRaises(ProgrammingError):
                app.persistence_policy

    def test_application_with_infrastructure(self):
        with self.construct_concrete_application() as app:

            # Start with a new table.
            app.drop_table()
            app.drop_table()
            app.setup_table()
            app.setup_table()

            # Check the notifications.
            reader = NotificationLogReader(app.notification_log)
            old_notifications = reader.list_notifications()
            len_old = len(old_notifications)

            # Check the application's persistence policy,
            # repository, and event store, are working.
            aggregate = ExampleAggregateRoot.__create__()
            aggregate.__save__()
            self.assertTrue(aggregate.id in app.repository)

            # Check the notifications.
            reader = NotificationLogReader(app.notification_log)
            notifications = reader.list_notifications()
            self.assertEqual(1 + len_old, len(notifications))
            topic = "eventsourcing.tests.core_tests.test_aggregate_root#ExampleAggregateRoot.Created"
            self.assertEqual(topic, notifications[len_old]["topic"])

            app.drop_table()

    def construct_concrete_application(self):
        return self.application_class.mixin(self.infrastructure_class)(
            cipher_key=encoded_random_bytes(16), persist_event_type=DomainEvent
        )

    def tearDown(self):
        # Check the close() method leaves everything unsubscribed.
        assert_event_handlers_empty()


class TestPopoApplication(TestSimpleApplication):
    infrastructure_class = PopoApplication


class TestDjangoApplication(DjangoTestCase, TestSimpleApplication):
    infrastructure_class = DjangoApplication


class TestAxonApplication(TestSimpleApplication):
    infrastructure_class = AxonApplication


class TestSnapshottingApplication(TestSimpleApplication):
    infrastructure_class = SnapshottingApplication.mixin(SQLAlchemyApplication)


class TestSnapshottingAxonApplication(TestSimpleApplication):
    infrastructure_class = SnapshottingApplication.mixin(AxonApplication)
