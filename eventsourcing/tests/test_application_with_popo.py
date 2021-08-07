import os
import sys
from datetime import datetime
from decimal import Decimal
from timeit import timeit
from unittest.case import TestCase
from uuid import UUID, uuid4

from eventsourcing.application import AggregateNotFound, Application
from eventsourcing.persistence import Transcoder, Transcoding
from eventsourcing.tests.test_aggregate import BankAccount, EmailAddress
from eventsourcing.utils import get_topic

TIMEIT_FACTOR = int(os.environ.get("TEST_TIMEIT_FACTOR", default=10))


class TestApplicationWithPOPO(TestCase):
    timeit_number = 100 * TIMEIT_FACTOR

    started_ats = {}
    counts = {}
    expected_factory_topic = "eventsourcing.popo:Factory"

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

    def test_example_application(self):
        app = BankAccounts(env={"IS_SNAPSHOTTING_ENABLED": "y"})

        self.assertFactoryTopic(app, self.expected_factory_topic)

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

        section = app.log["1,10"]
        self.assertEqual(len(section.items), 4)

        # Take snapshot (specify version).
        app.take_snapshot(account_id, version=2)

        snapshots = list(app.snapshots.get(account_id, desc=True, limit=1))
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].originator_version, 2)

        from_snapshot = app.repository.get(account_id, version=3)
        self.assertIsInstance(from_snapshot, BankAccount)
        self.assertEqual(from_snapshot.version, 3)
        self.assertEqual(from_snapshot.balance, Decimal("35.00"))

        # Take snapshot (don't specify version).
        app.take_snapshot(account_id)
        snapshots = list(app.snapshots.get(account_id, desc=True, limit=1))
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].originator_version, 4)

        from_snapshot = app.repository.get(account_id)
        self.assertIsInstance(from_snapshot, BankAccount)
        self.assertEqual(from_snapshot.version, 4)
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

    def assertFactoryTopic(self, app, expected_topic):
        self.assertEqual(get_topic(type(app.factory)), expected_topic)


class TestApplicationSnapshottingException(TestCase):
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
            if not isinstance(aggregate, BankAccount):
                raise self.AccountNotFoundError(account_id)
            return aggregate

    class AccountNotFoundError(Exception):
        pass
