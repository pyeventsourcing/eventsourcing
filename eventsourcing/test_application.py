import os
from decimal import Decimal
from unittest.case import TestCase
from uuid import uuid4

from eventsourcing.aggregate import BankAccount
from eventsourcing.bankaccounts import (
    BankAccounts,
)
from eventsourcing.infrastructurefactory import (
    InfrastructureFactory,
)


class TestApplication(TestCase):
    def setUp(self) -> None:
        os.environ[
            InfrastructureFactory.IS_SNAPSHOTTING_ENABLED
        ] = "yes"

    def tearDown(self) -> None:
        del os.environ[
            InfrastructureFactory.IS_SNAPSHOTTING_ENABLED
        ]

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

        from_snapshot = app.repository.get(
            account_id, at=3
        )
        self.assertIsInstance(from_snapshot, BankAccount)
        self.assertEqual(from_snapshot.version, 3)
        self.assertEqual(
            from_snapshot.balance, Decimal("35.00")
        )
