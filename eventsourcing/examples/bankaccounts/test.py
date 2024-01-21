from __future__ import annotations

import unittest
from decimal import Decimal
from uuid import uuid4

from eventsourcing.examples.bankaccounts.application import (
    AccountNotFoundError,
    BankAccounts,
)
from eventsourcing.examples.bankaccounts.domainmodel import (
    AccountClosedError,
    InsufficientFundsError,
)


class TestBankAccounts(unittest.TestCase):
    def test(self) -> None:
        app = BankAccounts()

        # Check account not found error.
        with self.assertRaises(AccountNotFoundError):
            app.get_balance(uuid4())

        # Create account #1.
        account_id1 = app.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Check balance of account #1.
        self.assertEqual(app.get_balance(account_id1), Decimal("0.00"))

        # Deposit funds in account #1.
        app.deposit_funds(
            credit_account_id=account_id1,
            amount=Decimal("200.00"),
        )

        # Check balance of account #1.
        self.assertEqual(app.get_balance(account_id1), Decimal("200.00"))

        # Withdraw funds from account #1.
        app.withdraw_funds(
            debit_account_id=account_id1,
            amount=Decimal("50.00"),
        )

        # Check balance of account #1.
        self.assertEqual(app.get_balance(account_id1), Decimal("150.00"))

        # Fail to withdraw funds from account #1- insufficient funds.
        with self.assertRaises(InsufficientFundsError):
            app.withdraw_funds(
                debit_account_id=account_id1,
                amount=Decimal("151.00"),
            )

        # Check balance of account #1 - should be unchanged.
        self.assertEqual(app.get_balance(account_id1), Decimal("150.00"))

        # Create account #2.
        account_id2 = app.open_account(
            full_name="Bob",
            email_address="bob@example.com",
        )

        # Transfer funds from account #1 to account #2.
        app.transfer_funds(
            debit_account_id=account_id1,
            credit_account_id=account_id2,
            amount=Decimal("100.00"),
        )

        # Check balances.
        self.assertEqual(app.get_balance(account_id1), Decimal("50.00"))
        self.assertEqual(app.get_balance(account_id2), Decimal("100.00"))

        # Fail to transfer funds - insufficient funds.
        with self.assertRaises(InsufficientFundsError):
            app.transfer_funds(
                debit_account_id=account_id1,
                credit_account_id=account_id2,
                amount=Decimal("1000.00"),
            )

        # Check balances - should be unchanged.
        self.assertEqual(app.get_balance(account_id1), Decimal("50.00"))
        self.assertEqual(app.get_balance(account_id2), Decimal("100.00"))

        # Close account #1.
        app.close_account(account_id1)

        # Fail to transfer funds - account #1 is closed.
        with self.assertRaises(AccountClosedError):
            app.transfer_funds(
                debit_account_id=account_id1,
                credit_account_id=account_id2,
                amount=Decimal("50.00"),
            )

        # Fail to withdraw funds - account #1 is closed.
        with self.assertRaises(AccountClosedError):
            app.withdraw_funds(
                debit_account_id=account_id1,
                amount=Decimal("1.00"),
            )

        # Fail to deposit funds - account #1 is closed.
        with self.assertRaises(AccountClosedError):
            app.deposit_funds(
                credit_account_id=account_id1,
                amount=Decimal("1000.00"),
            )

        # Fail to set overdraft limit on account #1 - account is closed.
        with self.assertRaises(AccountClosedError):
            app.set_overdraft_limit(
                account_id=account_id1,
                overdraft_limit=Decimal("500.00"),
            )

        # Check balances - should be unchanged.
        self.assertEqual(app.get_balance(account_id1), Decimal("50.00"))
        self.assertEqual(app.get_balance(account_id2), Decimal("100.00"))

        # Check overdraft limits - should be unchanged.
        self.assertEqual(
            app.get_overdraft_limit(account_id1),
            Decimal("0.00"),
        )
        self.assertEqual(
            app.get_overdraft_limit(account_id2),
            Decimal("0.00"),
        )

        # Set overdraft limit on account #2.
        app.set_overdraft_limit(
            account_id=account_id2,
            overdraft_limit=Decimal("500.00"),
        )

        # Can't set negative overdraft limit.
        with self.assertRaises(AssertionError):
            app.set_overdraft_limit(
                account_id=account_id2,
                overdraft_limit=Decimal("-500.00"),
            )

        # Check overdraft limit of account #2.
        self.assertEqual(
            app.get_overdraft_limit(account_id2),
            Decimal("500.00"),
        )

        # Withdraw funds from account #2.
        app.withdraw_funds(
            debit_account_id=account_id2,
            amount=Decimal("500.00"),
        )

        # Check balance of account #2 - should be overdrawn.
        self.assertEqual(
            app.get_balance(account_id2),
            Decimal("-400.00"),
        )

        # Fail to withdraw funds from account #2 - insufficient funds.
        with self.assertRaises(InsufficientFundsError):
            app.withdraw_funds(
                debit_account_id=account_id2,
                amount=Decimal("101.00"),
            )
