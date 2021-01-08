import os
from decimal import Decimal
from timeit import timeit
from unittest.case import TestCase
from uuid import UUID, uuid4

from eventsourcing.application import AggregateNotFoundError, Application
from eventsourcing.persistence import InfrastructureFactory
from eventsourcing.postgres import PostgresDatastore
from eventsourcing.tests.ramdisk import tmpfile_uris
from eventsourcing.tests.test_aggregate import BankAccount
from eventsourcing.tests.test_postgres import drop_postgres_table


class TestApplication(TestCase):
    def setUp(self) -> None:
        os.environ[InfrastructureFactory.IS_SNAPSHOTTING_ENABLED] = "yes"

    def tearDown(self) -> None:
        del os.environ[InfrastructureFactory.IS_SNAPSHOTTING_ENABLED]

    def test(self):
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

        # Take snapshot.
        app.take_snapshot(account_id, version=2)

        from_snapshot = app.repository.get(account_id, at=3)
        self.assertIsInstance(from_snapshot, BankAccount)
        self.assertEqual(from_snapshot.version, 3)
        self.assertEqual(from_snapshot.balance, Decimal("35.00"))

    def test_performance(self):

        app = BankAccounts()

        # Open an account.
        account_id = app.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )
        account = app.get_account(account_id)

        def insert():
            # Credit the account.
            account.append_transaction(Decimal("10.00"))
            app.save(account)

        # Warm up.
        number = 10
        timeit(insert, number=number)

        number = 500
        duration = timeit(insert, number=number)
        print(self, f"{duration / number:.9f}")


class TestApplicationWithSQLite(TestApplication):
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
        return account.uuid

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
        except AggregateNotFoundError:
            raise self.AccountNotFoundError(account_id)
        else:
            if not isinstance(aggregate, BankAccount):
                raise self.AccountNotFoundError(account_id)
            return aggregate

    class AccountNotFoundError(Exception):
        pass
