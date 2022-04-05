import traceback
import warnings
from concurrent.futures import ThreadPoolExecutor
from threading import Event, get_ident
from time import sleep
from unittest.case import TestCase
from uuid import uuid4

from eventsourcing.application import Application, ProcessEvent, ProcessingEvent
from eventsourcing.domain import Aggregate
from eventsourcing.persistence import InfrastructureFactory, IntegrityError
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

        max_id = app.recorder.max_notification_id()

        recordings = app.save(Aggregate())
        self.assertEqual(len(recordings), 1)
        self.assertEqual(recordings[0].notification.id, 1 + max_id)

        recordings = app.save(Aggregate())
        self.assertEqual(len(recordings), 1)
        self.assertEqual(recordings[0].notification.id, 2 + max_id)

        recordings = app.save(Aggregate(), Aggregate())
        self.assertEqual(len(recordings), 2)
        self.assertEqual(recordings[0].notification.id, 3 + max_id)
        self.assertEqual(recordings[1].notification.id, 4 + max_id)

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

    def test_application_with_cached_aggregates_and_fastforward(self):
        app = Application(env={"AGGREGATE_CACHE_MAXSIZE": "10"})

        aggregate = Aggregate()
        app.save(aggregate)
        # Should not put the aggregate in the cache.
        with self.assertRaises(KeyError):
            self.assertEqual(aggregate, app.repository.cache.get(aggregate.id))

        # Getting the aggregate should put aggregate in the cache.
        app.repository.get(aggregate.id)
        self.assertEqual(aggregate, app.repository.cache.get(aggregate.id))

        # Triggering a subsequent event shouldn't update the cache.
        aggregate.trigger_event(Aggregate.Event)
        app.save(aggregate)
        self.assertNotEqual(aggregate, app.repository.cache.get(aggregate.id))
        self.assertEqual(
            aggregate.version, app.repository.cache.get(aggregate.id).version + 1
        )

        # Getting the aggregate should fastforward the aggregate in the cache.
        app.repository.get(aggregate.id)
        self.assertEqual(aggregate, app.repository.cache.get(aggregate.id))

    def test_application_fastforward_skipped_during_contention(self):
        app = Application(env={"AGGREGATE_CACHE_MAXSIZE": "10"})

        aggregate = Aggregate()
        aggregate_id = aggregate.id
        app.save(aggregate)

        stopped = Event()

        # Trigger, save, get, check.
        def trigger_save_get_check():
            while not stopped.is_set():
                try:
                    aggregate = app.repository.get(aggregate_id)
                    aggregate.trigger_event(Aggregate.Event)
                    saved_version = aggregate.version
                    try:
                        app.save(aggregate)
                    except IntegrityError:
                        continue
                    if saved_version != app.repository.get(aggregate_id).version:
                        print(f"Skipped fast-forwarding at version {saved_version}")
                        stopped.set()
                    if aggregate.version % 1000 == 0:
                        print("Version:", aggregate.version, get_ident())
                    sleep(0.001)
                except BaseException:
                    print(traceback.format_exc())
                    raise

        executor = ThreadPoolExecutor(max_workers=100)
        for _ in range(100):
            executor.submit(trigger_save_get_check)

        if not stopped.wait(timeout=100):
            stopped.set()
            self.fail("Didn't skip fast forwarding before test timed out...")
        executor.shutdown()

    def test_application_with_cached_aggregates_not_fastforward(self):
        app = Application(
            env={
                "AGGREGATE_CACHE_MAXSIZE": "10",
                "AGGREGATE_CACHE_FASTFORWARD": "f",
            }
        )
        aggregate = Aggregate()
        app.save(aggregate)
        # Should put the aggregate in the cache.
        self.assertEqual(aggregate, app.repository.cache.get(aggregate.id))
        app.repository.get(aggregate.id)
        self.assertEqual(aggregate, app.repository.cache.get(aggregate.id))

    def test_application_log(self):
        # Check the old 'log' attribute presents the 'notification log' object.
        app = Application()

        # Verify deprecation warning.
        with warnings.catch_warnings(record=True) as w:
            self.assertIs(app.log, app.notification_log)

        self.assertEqual(1, len(w))
        self.assertIs(w[-1].category, DeprecationWarning)
        self.assertEqual(
            "'log' is deprecated, use 'notifications' instead", w[-1].message.args[0]
        )

    def test_process_event_class(self):
        # Check the old 'ProcessEvent' class still works.
        self.assertTrue(issubclass(ProcessEvent, ProcessingEvent))


class TestApplicationWithPOPO(ExampleApplicationTestCase):
    expected_factory_topic = "eventsourcing.popo:Factory"


del ExampleApplicationTestCase
