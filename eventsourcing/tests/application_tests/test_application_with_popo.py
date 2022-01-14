from unittest.case import TestCase
from uuid import uuid4

from eventsourcing.application import Application
from eventsourcing.domain import Aggregate
from eventsourcing.persistence import InfrastructureFactory
from eventsourcing.tests.application import ExampleApplicationTestCase


class TestApplication(TestCase):
    def test_name(self):
        self.assertEqual(Application.name, "Application")

        class MyApplication1(Application):
            pass

        self.assertEqual(MyApplication1.name, "MyApplication1")

        class MyApplication2(Application):
            name = "MyBoundedContext"

        self.assertEqual(MyApplication2.name, "MyBoundedContext")

    def test_resolve_persistence_topics(self):
        # None specified.
        app = Application()
        self.assertIsInstance(app.factory, InfrastructureFactory)

        # Legacy 'INFRASTRUCTURE_FACTORY'.
        app = Application(env={"INFRASTRUCTURE_FACTORY": "eventsourcing.popo:Factory"})
        self.assertIsInstance(app.factory, InfrastructureFactory)

        # Legacy 'FACTORY_TOPIC'.
        app = Application(env={"FACTORY_TOPIC": "eventsourcing.popo:Factory"})
        self.assertIsInstance(app.factory, InfrastructureFactory)

        # Check 'PERSISTENCE_MODULE' resolves to a class.
        app = Application(env={"PERSISTENCE_MODULE": "eventsourcing.popo"})
        self.assertIsInstance(app.factory, InfrastructureFactory)

        # Check exceptions.
        with self.assertRaises(AssertionError) as cm:
            Application(env={"PERSISTENCE_MODULE": "eventsourcing.application"})
        self.assertEqual(
            cm.exception.args[0],
            (
                "Found 0 infrastructure factory classes in "
                "'eventsourcing.application', expected 1."
            ),
        )

        with self.assertRaises(AssertionError) as cm:
            Application(
                env={"PERSISTENCE_MODULE": "eventsourcing.application:Application"}
            )
        self.assertEqual(
            cm.exception.args[0],
            (
                "Not an infrastructure factory class or module: "
                "eventsourcing.application:Application"
            ),
        )

    def test_save_returns_recording_event(self):
        app = Application()

        recordings = app.save()
        self.assertEqual(recordings, [])

        recordings = app.save(None)
        self.assertEqual(recordings, [])

        recordings = app.save(Aggregate())
        self.assertEqual(len(recordings), 1)
        self.assertEqual(recordings[0].notification.id, 1)

        recordings = app.save(Aggregate())
        self.assertEqual(len(recordings), 1)
        self.assertEqual(recordings[0].notification.id, 2)

        recordings = app.save(Aggregate(), Aggregate())
        self.assertEqual(len(recordings), 2)
        self.assertEqual(recordings[0].notification.id, 3)
        self.assertEqual(recordings[1].notification.id, 4)

    def test_take_snapshot_raises_assertion_error_if_snapshotting_not_enabled(self):
        app = Application()
        with self.assertRaises(AssertionError) as cm:
            app.take_snapshot(uuid4())
        self.assertEqual(
            cm.exception.args[0],
            (
                "Can't take snapshot without snapshots store. Please "
                "set environment variable IS_SNAPSHOTTING_ENABLED to "
                "a true value (e.g. 'y'), or set 'is_snapshotting_enabled' "
                "on application class, or set 'snapshotting_intervals' on "
                "application class."
            ),
        )

    def test_application_with_cached_aggregates(self):
        app = Application(env={"AGGREGATE_CACHE_MAXSIZE": "10"})

        aggregate = Aggregate()
        app.save(aggregate)
        self.assertEqual(aggregate, app.repository.cache.get(aggregate.id))

    def test_application_log(self):
        app = Application()
        self.assertEqual(app.log, app.notifications)


class TestApplicationWithPOPO(ExampleApplicationTestCase):
    expected_factory_topic = "eventsourcing.popo:Factory"


del ExampleApplicationTestCase
