import os
from decimal import Decimal
from timeit import timeit
from unittest.case import TestCase
from uuid import UUID, uuid4

from eventsourcing.application import AggregateNotFound, Application
from eventsourcing.persistence import InfrastructureFactory
from eventsourcing.postgres import PostgresDatastore
from eventsourcing.tests.ramdisk import tmpfile_uris
from eventsourcing.tests.test_aggregate import BankAccount
from eventsourcing.tests.test_postgres import drop_postgres_table


class TestApplication(TestCase):
    timeit_number = 10000

    def setUp(self) -> None:
        os.environ[InfrastructureFactory.IS_SNAPSHOTTING_ENABLED] = "yes"

    def tearDown(self) -> None:
        if InfrastructureFactory.IS_SNAPSHOTTING_ENABLED in os.environ:
            del os.environ[InfrastructureFactory.IS_SNAPSHOTTING_ENABLED]

    def test_example_application(self):
        app = BankAccounts()

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

    def test_put_performance(self):

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
        print(
            self,
            f"{1000 * duration / self.timeit_number:.3f}ms",
            f"{self.timeit_number / duration:.0f}/s",
        )

    def test_get_performance_with_snapshotting_enabled(self):
        self._test_get_performance()

    def test_get_performance_without_snapshotting_enabled(self):
        del os.environ[InfrastructureFactory.IS_SNAPSHOTTING_ENABLED]
        self._test_get_performance()

    def _test_get_performance(self):

        app = BankAccounts()

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
        print(
            self,
            f"{1000 * duration / self.timeit_number:.3f}ms",
            f"{self.timeit_number / duration:.0f}/s",
        )


class TestApplicationSnapshottingException(TestCase):
    def test_take_snapshot_raises_assertion_error_if_snapshotting_not_enabled(self):
        app = Application()
        with self.assertRaises(AssertionError) as cm:
            app.take_snapshot(uuid4())
        self.assertEqual(
            cm.exception.args[0],
            (
                "Can't take snapshot without snapshots store. "
                "Please set environment variable IS_SNAPSHOTTING_ENABLED "
                "to a true value (e.g. 'y')."
            ),
        )


class TestApplicationWithSQLite(TestApplication):
    timeit_number = 2000

    def setUp(self) -> None:
        super().setUp()
        self.uris = tmpfile_uris()
        # self.db_uri = next(self.uris)

        os.environ["INFRASTRUCTURE_FACTORY"] = "eventsourcing.sqlite:Factory"
        os.environ["DO_CREATE_TABLE"] = "y"
        os.environ["SQLITE_DBNAME"] = next(self.uris)

    def tearDown(self) -> None:
        del os.environ["INFRASTRUCTURE_FACTORY"]
        del os.environ["DO_CREATE_TABLE"]
        del os.environ["SQLITE_DBNAME"]
        super().tearDown()


class TestApplicationWithPostgres(TestApplication):
    timeit_number = 1000

    def setUp(self) -> None:
        super().setUp()
        self.uris = tmpfile_uris()

        os.environ["INFRASTRUCTURE_FACTORY"] = "eventsourcing.postgres:Factory"
        os.environ["DO_CREATE_TABLE"] = "y"
        os.environ["POSTGRES_DBNAME"] = "eventsourcing"
        os.environ["POSTGRES_HOST"] = "127.0.0.1"
        os.environ["POSTGRES_USER"] = "eventsourcing"
        os.environ["POSTGRES_PASSWORD"] = "eventsourcing"

        db = PostgresDatastore(
            os.getenv("POSTGRES_DBNAME"),
            os.getenv("POSTGRES_HOST"),
            os.getenv("POSTGRES_USER"),
            os.getenv("POSTGRES_PASSWORD"),
        )
        drop_postgres_table(db, "bankaccounts_events")
        drop_postgres_table(db, "bankaccounts_snapshots")

    def tearDown(self) -> None:
        del os.environ["INFRASTRUCTURE_FACTORY"]
        del os.environ["DO_CREATE_TABLE"]
        del os.environ["POSTGRES_DBNAME"]
        del os.environ["POSTGRES_HOST"]
        del os.environ["POSTGRES_USER"]
        del os.environ["POSTGRES_PASSWORD"]
        super().tearDown()


class BankAccounts(Application):
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
