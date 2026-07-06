from __future__ import annotations

import traceback
import warnings
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Event, get_ident
from time import sleep
from typing import TYPE_CHECKING, Any, ClassVar
from unittest import TestCase
from uuid import UUID, uuid4

from eventsourcing.application import AggregateNotFoundError, Application
from eventsourcing.domain import Aggregate
from eventsourcing.persistence import (
    InfrastructureFactory,
    InfrastructureFactoryError,
    IntegrityError,
    JSONTranscoder,
    Transcoding,
)
from eventsourcing.tests.domain import BankAccount, EmailAddress
from eventsourcing.utils import EnvType, get_topic

if TYPE_CHECKING:
    from datetime import datetime


class ExampleApplicationTestCase(TestCase):
    started_ats: ClassVar[dict[type[TestCase], datetime]] = {}
    counts: ClassVar[dict[type[TestCase], int]] = {}
    expected_factory_topic: str

    def test_example_application(self) -> None:
        app = BankAccounts(env={"IS_SNAPSHOTTING_ENABLED": "y"})

        self.assertEqual(get_topic(type(app.factory)), self.expected_factory_topic)

        # Check AccountNotFound exception.
        with self.assertRaises(BankAccounts.AccountNotFoundError):
            app.get_account(uuid4())

        # Open an account.
        account_id = app.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Check balance.
        self.assertEqual(
            app.get_balance(account_id),
            Decimal("0.00"),
        )

        # Credit the account.
        app.credit_account(account_id, Decimal("10.00"))

        # Check balance.
        self.assertEqual(
            app.get_balance(account_id),
            Decimal("10.00"),
        )

        app.credit_account(account_id, Decimal("25.00"))
        app.credit_account(account_id, Decimal("30.00"))

        # Check balance.
        self.assertEqual(
            app.get_balance(account_id),
            Decimal("65.00"),
        )

        # sleep(1)  # Added to make eventsourcing-axon tests work.
        section = app.notification_log["1,10"]
        self.assertEqual(len(section.items), 4)

        # Take snapshot (specify version).
        app.take_snapshot(
            account_id, BankAccount, version=Aggregate.INITIAL_VERSION + 1
        )

        assert app.snapshots is not None  # for mypy
        snapshots = list(app.snapshots.get(account_id))
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].originator_version, Aggregate.INITIAL_VERSION + 1)

        from_snapshot1 = app.repository.get(
            account_id, BankAccount, version=Aggregate.INITIAL_VERSION + 2
        )
        self.assertIsInstance(from_snapshot1, BankAccount)
        self.assertEqual(from_snapshot1.version, Aggregate.INITIAL_VERSION + 2)
        self.assertEqual(from_snapshot1.balance, Decimal("35.00"))

        # Take snapshot (don't specify version).
        app.take_snapshot(account_id, BankAccount)
        assert app.snapshots is not None  # for mypy
        snapshots = list(app.snapshots.get(account_id))
        self.assertEqual(len(snapshots), 2)
        self.assertEqual(snapshots[0].originator_version, Aggregate.INITIAL_VERSION + 1)
        self.assertEqual(snapshots[1].originator_version, Aggregate.INITIAL_VERSION + 3)

        from_snapshot2 = app.repository.get(account_id, BankAccount)
        self.assertIsInstance(from_snapshot2, BankAccount)
        self.assertEqual(from_snapshot2.version, Aggregate.INITIAL_VERSION + 3)
        self.assertEqual(from_snapshot2.balance, Decimal("65.00"))


class EmailAddressAsStr(Transcoding):
    type = EmailAddress
    name = "email_address_as_str"

    def encode(self, obj: EmailAddress) -> str:
        return obj.address

    def decode(self, data: str) -> EmailAddress:
        return EmailAddress(data)


class BankAccounts(Application):
    is_snapshotting_enabled = True

    def register_transcodings(self, transcoder: JSONTranscoder) -> None:
        super().register_transcodings(transcoder)
        transcoder.register(EmailAddressAsStr())

    def open_account(self, full_name: str, email_address: str) -> UUID:
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
            aggregate = self.repository.get(account_id, BankAccount)
        except AggregateNotFoundError:
            raise self.AccountNotFoundError(account_id) from None
        else:
            assert isinstance(aggregate, BankAccount)
            return aggregate

    class AccountNotFoundError(Exception):
        pass


class ApplicationTestCase(TestCase):
    def test_name(self) -> None:
        self.assertEqual(Application.name, "Application")

        class MyApplication1(Application):
            pass

        self.assertEqual(MyApplication1.name, "MyApplication1")

        class MyApplication2(Application):
            name = "MyBoundedContext"

        self.assertEqual(MyApplication2.name, "MyBoundedContext")

    def test_as_context_manager(self) -> None:
        with Application():
            pass

    def test_resolve_persistence_topics(self) -> None:
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
        with self.assertRaises(InfrastructureFactoryError) as cm:
            Application(env={"PERSISTENCE_MODULE": "eventsourcing.application"})
        self.assertEqual(
            cm.exception.args[0],
            "Found 0 infrastructure factory classes in "
            "'eventsourcing.application', expected 1.",
        )

        with self.assertRaises(InfrastructureFactoryError) as cm:
            Application(
                env={"PERSISTENCE_MODULE": "eventsourcing.application:Application"}
            )
        self.assertEqual(
            "Topic 'eventsourcing.application:Application' didn't "
            "resolve to a persistence module or infrastructure factory class: "
            "<class 'eventsourcing.application.Application'>",
            cm.exception.args[0],
        )

    def test_save_returns_recording_event(self) -> None:
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

    def test_take_snapshot_raises_assertion_error_if_snapshotting_not_enabled(
        self,
    ) -> None:
        app = Application()
        with self.assertRaises(AssertionError) as cm:
            app.take_snapshot(uuid4())
        self.assertEqual(
            cm.exception.args[0],
            "Can't take snapshot without snapshots store. Please "
            "set environment variable IS_SNAPSHOTTING_ENABLED to "
            "a true value (e.g. 'y'), or set 'is_snapshotting_enabled' "
            "on application class, or set 'snapshotting_intervals' on "
            "application class.",
        )

    def test_application_with_cached_aggregates_and_fastforward(self) -> None:
        app = Application(env={"AGGREGATE_CACHE_MAXSIZE": "10"})

        aggregate = Aggregate()
        app.save(aggregate)
        # Should not put the aggregate in the cache.
        assert app.repository.cache is not None  # for mypy
        with self.assertRaises(KeyError):
            self.assertEqual(aggregate, app.repository.cache.get(aggregate.id))

        # Getting the aggregate should put aggregate in the cache.
        app.repository.get(aggregate.id, Aggregate)
        self.assertEqual(aggregate, app.repository.cache.get(aggregate.id))

        # Triggering a subsequent event shouldn't update the cache.
        aggregate.trigger_event(Aggregate.Event)
        app.save(aggregate)
        self.assertNotEqual(aggregate, app.repository.cache.get(aggregate.id))
        self.assertEqual(
            aggregate.version, app.repository.cache.get(aggregate.id).version + 1
        )

        # Getting the aggregate should fastforward the aggregate in the cache.
        app.repository.get(aggregate.id, Aggregate)
        self.assertEqual(aggregate, app.repository.cache.get(aggregate.id))

    def test_check_aggregate_fastforwarding_nonblocking(self) -> None:
        self._check_aggregate_fastforwarding_during_contention(
            env={
                "AGGREGATE_CACHE_MAXSIZE": "10",
                "AGGREGATE_CACHE_FASTFORWARD_SKIPPING": "y",
            }
        )

    def test_check_aggregate_fastforwarding_blocking(self) -> None:
        self._check_aggregate_fastforwarding_during_contention(
            env={"AGGREGATE_CACHE_MAXSIZE": "10"}
        )

    def _check_aggregate_fastforwarding_during_contention(self, env: EnvType) -> None:
        app = Application(env=env)

        self.assertEqual(len(app.repository._fastforward_locks_inuse), 0)

        # Create one aggregate.
        original_aggregate = Aggregate()
        app.save(original_aggregate)
        obj_ids = set()

        # Prime the cache.
        app.repository.get(original_aggregate.id, Aggregate)

        # Remember the aggregate ID.
        aggregate_id = original_aggregate.id

        stopped = Event()
        errors: list[BaseException] = []
        successful_thread_ids = set()

        def trigger_save_get_check() -> None:
            while not stopped.is_set():
                try:
                    # Get the aggregate.
                    aggregate = app.repository.get(aggregate_id, Aggregate)
                    original_version = aggregate.version

                    # Try to record a new event.
                    aggregate.trigger_event(Aggregate.Event)
                    # Give other threads a chance.
                    try:
                        app.save(aggregate)
                    except IntegrityError:
                        # Start again if we didn't record a new event.
                        # print("Got integrity error")
                        sleep(0.001)
                        continue

                    # Get the aggregate from the cache.
                    assert app.repository.cache is not None
                    cached: Any = app.repository.cache.get(aggregate_id)
                    obj_ids.add(id(cached))

                    if len(obj_ids) > 1:
                        stopped.set()
                        continue

                    # Fast-forward the cached aggregate.
                    fastforwarded = app.repository.get(aggregate_id, Aggregate)

                    # Check cached aggregate was fast-forwarded with recorded event.
                    if fastforwarded.version < original_version:
                        try:
                            self.fail(
                                f"Failed to fast-forward at version {original_version}"
                            )
                        except AssertionError as e:
                            errors.append(e)
                            stopped.set()
                            continue

                    # Monitor number of threads getting involved.
                    thread_id = get_ident()
                    successful_thread_ids.add(thread_id)

                    # print("Version:", aggregate.version, thread_id)

                    # See if we have done enough.
                    if len(successful_thread_ids) > 10 and aggregate.version >= 25:
                        stopped.set()
                        continue

                    sleep(0.0001)
                    # sleep(0.001)
                except BaseException as e:
                    errors.append(e)
                    stopped.set()
                    print(traceback.format_exc())
                    raise

        executor = ThreadPoolExecutor(max_workers=100)
        futures = []
        for _ in range(100):
            f = executor.submit(trigger_save_get_check)
            futures.append(f)

        # Run for three seconds.
        stopped.wait(timeout=10)
        for f in futures:
            f.result()
        # print("Got all results, shutting down executor")
        executor.shutdown()

        try:
            if errors:
                raise errors[0]
            if len(obj_ids) > 1:
                self.fail(f"More than one instance used in the cache: {len(obj_ids)}")
            if len(successful_thread_ids) < 3:
                self.fail("Insufficient sharing across contentious threads")

            final_aggregate = app.repository.get(aggregate_id, Aggregate)
            # print("Final aggregate version:", final_aggregate.version)
            if final_aggregate.version < 25:
                self.fail(f"Insufficient version increment: {final_aggregate.version}")

            self.assertEqual(len(app.repository._fastforward_locks_inuse), 0)

        finally:
            # print("Closing application")
            app.close()

    def test_application_with_cached_aggregates_not_fastforward(self) -> None:
        app = Application[UUID](
            env={
                "AGGREGATE_CACHE_MAXSIZE": "10",
                "AGGREGATE_CACHE_FASTFORWARD": "f",
            }
        )
        aggregate1 = Aggregate()
        app.save(aggregate1)
        aggregate_id = aggregate1.id

        # Should put the aggregate in the cache.
        assert app.repository.cache is not None  # for mypy
        self.assertEqual(aggregate1, app.repository.cache.get(aggregate_id))
        app.repository.get(aggregate_id, Aggregate)
        self.assertEqual(aggregate1, app.repository.cache.get(aggregate_id))

        aggregate2 = Aggregate()
        aggregate2._id = aggregate_id
        aggregate2.trigger_event(Aggregate.Event)

        # This will replace object in cache.
        app.save(aggregate2)

        self.assertEqual(aggregate2.version, aggregate1.version + 1)
        aggregate3: Aggregate = app.repository.get(aggregate_id, Aggregate)
        self.assertEqual(aggregate3.version, aggregate3.version)
        self.assertEqual(id(aggregate3.version), id(aggregate3.version))

        # This will mess things up because the cache has a stale aggregate.
        aggregate3.trigger_event(Aggregate.Event)
        app.events.put(aggregate3.collect_events())

        # And so using the aggregate to record new events will cause an IntegrityError.
        aggregate4: Aggregate = app.repository.get(aggregate_id, Aggregate)
        aggregate4.trigger_event(Aggregate.Event)
        with self.assertRaises(IntegrityError):
            app.save(aggregate4)

    def test_application_with_deepcopy_from_cache_arg(self) -> None:
        app = Application[UUID](
            env={
                "AGGREGATE_CACHE_MAXSIZE": "10",
            }
        )
        aggregate = Aggregate()
        app.save(aggregate)
        self.assertEqual(aggregate.version, 1)
        reconstructed: Aggregate = app.repository.get(aggregate.id, Aggregate)
        reconstructed.version = 101
        assert app.repository.cache is not None  # for mypy
        self.assertEqual(app.repository.cache.get(aggregate.id).version, 1)
        cached = app.repository.get(aggregate.id, Aggregate, deepcopy_from_cache=False)
        cached.version = 101
        self.assertEqual(app.repository.cache.get(aggregate.id).version, 101)

    def test_application_with_deepcopy_from_cache_attribute(self) -> None:
        app = Application[UUID](
            env={
                "AGGREGATE_CACHE_MAXSIZE": "10",
            }
        )
        aggregate = Aggregate()
        app.save(aggregate)
        self.assertEqual(aggregate.version, 1)
        reconstructed: Aggregate = app.repository.get(aggregate.id, Aggregate)
        reconstructed.version = 101
        assert app.repository.cache is not None  # for mypy
        self.assertEqual(app.repository.cache.get(aggregate.id).version, 1)
        app.repository.deepcopy_from_cache = False
        cached: Aggregate = app.repository.get(aggregate.id, Aggregate)
        cached.version = 101
        self.assertEqual(app.repository.cache.get(aggregate.id).version, 101)

    def test_application_log(self) -> None:
        # Check the old 'log' attribute presents the 'notification log' object.
        app = Application[UUID]()

        # Verify deprecation warning.
        with warnings.catch_warnings(record=True) as w:
            self.assertIs(app.log, app.notification_log)

        self.assertEqual(1, len(w))
        self.assertIs(w[-1].category, DeprecationWarning)
        self.assertIn(
            "'log' is deprecated, use 'notification_log' instead", str(w[-1].message)
        )
