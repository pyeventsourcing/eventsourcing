import os
import sys
import traceback
import warnings
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from decimal import Decimal
from threading import Event, get_ident
from time import sleep
from timeit import timeit
from unittest import TestCase
from uuid import UUID, uuid4

from eventsourcing.application import (
    AggregateNotFound,
    Application,
    ProcessEvent,
    ProcessingEvent,
)
from eventsourcing.domain import Aggregate
from eventsourcing.persistence import (
    InfrastructureFactory,
    IntegrityError,
    Transcoder,
    Transcoding,
)
from eventsourcing.tests.domain import BankAccount, EmailAddress
from eventsourcing.utils import get_topic

TIMEIT_FACTOR = int(os.environ.get("TEST_TIMEIT_FACTOR", default=10))


class ExampleApplicationTestCase(TestCase):
    timeit_number = TIMEIT_FACTOR
    started_ats = {}
    counts = {}
    expected_factory_topic: str

    def test_example_application(self):
        app = BankAccounts(env={"IS_SNAPSHOTTING_ENABLED": "y"})
        max_notification_id = app.recorder.max_notification_id()

        self.assertEqual(get_topic(type(app.factory)), self.expected_factory_topic)

        # Check AccountNotFound exception.
        with self.assertRaises(BankAccounts.AccountNotFoundError):
            app.get_account(uuid4())

        # Open an account.
        account_id = app.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Credit the account.
        app.credit_account(account_id, Decimal("10.00"))
        app.credit_account(account_id, Decimal("25.00"))
        app.credit_account(account_id, Decimal("30.00"))

        # Check balance.
        self.assertEqual(
            app.get_balance(account_id),
            Decimal("65.00"),
        )

        sleep(1)  # Added to make eventsourcing-axon tests work, perhaps not necessary.
        section = app.notification_log[
            f"{max_notification_id + 1},{max_notification_id + 10}"
        ]
        self.assertEqual(len(section.items), 4)

        # Take snapshot (specify version).
        app.take_snapshot(account_id, version=Aggregate.INITIAL_VERSION + 1)

        snapshots = list(app.snapshots.get(account_id))
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].originator_version, Aggregate.INITIAL_VERSION + 1)

        from_snapshot = app.repository.get(
            account_id, version=Aggregate.INITIAL_VERSION + 2
        )
        self.assertIsInstance(from_snapshot, BankAccount)
        self.assertEqual(from_snapshot.version, Aggregate.INITIAL_VERSION + 2)
        self.assertEqual(from_snapshot.balance, Decimal("35.00"))

        # Take snapshot (don't specify version).
        app.take_snapshot(account_id)
        snapshots = list(app.snapshots.get(account_id))
        self.assertEqual(len(snapshots), 2)
        self.assertEqual(snapshots[0].originator_version, Aggregate.INITIAL_VERSION + 1)
        self.assertEqual(snapshots[1].originator_version, Aggregate.INITIAL_VERSION + 3)

        from_snapshot = app.repository.get(account_id)
        self.assertIsInstance(from_snapshot, BankAccount)
        self.assertEqual(from_snapshot.version, Aggregate.INITIAL_VERSION + 3)
        self.assertEqual(from_snapshot.balance, Decimal("65.00"))

    def test__put_performance(self):

        app = BankAccounts()

        # Open an account.
        account_id = app.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )
        account = app.get_account(account_id)

        def put():
            # Credit the account.
            account.append_transaction(Decimal("10.00"))
            app.save(account)

        # Warm up.
        number = 10
        timeit(put, number=number)

        duration = timeit(put, number=self.timeit_number)
        self.print_time("store events", duration)

    def test__get_performance_with_snapshotting_enabled(self):
        print()
        self._test_get_performance(is_snapshotting_enabled=True)

    def test__get_performance_without_snapshotting_enabled(self):
        self._test_get_performance(is_snapshotting_enabled=False)

    def _test_get_performance(self, is_snapshotting_enabled: bool):

        app = BankAccounts(
            env={"IS_SNAPSHOTTING_ENABLED": "y" if is_snapshotting_enabled else "n"}
        )

        # Open an account.
        account_id = app.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        def read():
            # Get the account.
            app.get_account(account_id)

        # Warm up.
        timeit(read, number=10)

        duration = timeit(read, number=self.timeit_number)

        if is_snapshotting_enabled:
            test_label = "get with snapshotting"
        else:
            test_label = "get without snapshotting"
        self.print_time(test_label, duration)

    def print_time(self, test_label, duration):
        cls = type(self)
        if cls not in self.started_ats:
            self.started_ats[cls] = datetime.now()
            print(f"{cls.__name__: <29} timeit number: {cls.timeit_number}")
            self.counts[cls] = 1
        else:
            self.counts[cls] += 1

        rate = f"{self.timeit_number / duration:.0f} events/s"
        print(
            f"{cls.__name__: <29}",
            f"{test_label: <21}",
            f"{rate: >15}",
            f"  {1000 * duration / self.timeit_number:.3f} ms/event",
        )

        if self.counts[cls] == 3:
            duration = datetime.now() - cls.started_ats[cls]
            print(f"{cls.__name__: <29} timeit duration: {duration}")
            sys.stdout.flush()


class EmailAddressAsStr(Transcoding):
    type = EmailAddress
    name = "email_address_as_str"

    def encode(self, obj: EmailAddress) -> str:
        return obj.address

    def decode(self, data: str) -> EmailAddress:
        return EmailAddress(data)


class BankAccounts(Application):
    is_snapshotting_enabled = True

    def register_transcodings(self, transcoder: Transcoder) -> None:
        super(BankAccounts, self).register_transcodings(transcoder)
        transcoder.register(EmailAddressAsStr())

    def open_account(self, full_name, email_address):
        account = BankAccount.open(
            full_name=full_name,
            email_address=email_address,
        )
        self.save(account)
        return account.id

    def credit_account(self, account_id: UUID, amount: Decimal) -> None:
        account = self.get_account(account_id)
        account.append_transaction(amount)
        self.save(account)

    def get_balance(self, account_id: UUID) -> Decimal:
        account = self.get_account(account_id)
        return account.balance

    def get_account(self, account_id: UUID) -> BankAccount:
        try:
            aggregate = self.repository.get(account_id)
        except AggregateNotFound:
            raise self.AccountNotFoundError(account_id)
        else:
            assert isinstance(aggregate, BankAccount)
            return aggregate

    class AccountNotFoundError(Exception):
        pass


class ApplicationTestCase(TestCase):
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

    def test_application_fastforward_skipping_during_contention(self):
        app = Application(
            env={
                "AGGREGATE_CACHE_MAXSIZE": "10",
                "AGGREGATE_CACHE_FASTFORWARD_SKIPPING": "y",
            }
        )

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
                    cached_version = app.repository.get(aggregate_id).version
                    if saved_version > cached_version:
                        print(f"Skipped fast-forwarding at version {saved_version}")
                        stopped.set()
                    if aggregate.version % 1000 == 0:
                        print("Version:", aggregate.version, get_ident())
                    sleep(0.00)
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

    def test_application_fastforward_blocking_during_contention(self):
        app = Application(
            env={
                "AGGREGATE_CACHE_MAXSIZE": "10",
            }
        )

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
                    cached_version = app.repository.get(aggregate_id).version
                    if saved_version > cached_version:
                        print(f"Skipped fast-forwarding at version {saved_version}")
                        stopped.set()
                    if aggregate.version % 1000 == 0:
                        print("Version:", aggregate.version, get_ident())
                    sleep(0.00)
                except BaseException:
                    print(traceback.format_exc())
                    raise

        executor = ThreadPoolExecutor(max_workers=100)
        for _ in range(100):
            executor.submit(trigger_save_get_check)

        if not stopped.wait(timeout=3):
            stopped.set()
        else:
            self.fail("Wrongly skipped fast forwarding")
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

    def test_application_with_deepcopy_from_cache_arg(self):
        app = Application(
            env={
                "AGGREGATE_CACHE_MAXSIZE": "10",
            }
        )
        aggregate = Aggregate()
        app.save(aggregate)
        self.assertEqual(aggregate.version, 1)
        aggregate = app.repository.get(aggregate.id)
        aggregate.version = 101
        self.assertEqual(app.repository.cache.get(aggregate.id).version, 1)
        aggregate = app.repository.get(aggregate.id, deepcopy_from_cache=False)
        aggregate.version = 101
        self.assertEqual(app.repository.cache.get(aggregate.id).version, 101)

    def test_application_with_deepcopy_from_cache_attribute(self):
        app = Application(
            env={
                "AGGREGATE_CACHE_MAXSIZE": "10",
            }
        )
        aggregate = Aggregate()
        app.save(aggregate)
        self.assertEqual(aggregate.version, 1)
        aggregate = app.repository.get(aggregate.id)
        aggregate.version = 101
        self.assertEqual(app.repository.cache.get(aggregate.id).version, 1)
        app.repository.deepcopy_from_cache = False
        aggregate = app.repository.get(aggregate.id)
        aggregate.version = 101
        self.assertEqual(app.repository.cache.get(aggregate.id).version, 101)

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
