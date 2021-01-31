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
    def test(self):
        app = BankAccounts()

        # Check account not found error.
        with self.assertRaises(AccountNotFoundError):
            app.get_balance(uuid4())

        # Create an account.
        account_id1 = app.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Check balance.
        self.assertEqual(app.get_balance(account_id1), Decimal("0.00"))

        # Deposit funds.
        app.deposit_funds(
            credit_account_id=account_id1,
            amount=Decimal("200.00"),
        )

        # Check balance.
        self.assertEqual(app.get_balance(account_id1), Decimal("200.00"))

        # Withdraw funds.
        app.withdraw_funds(
            debit_account_id=account_id1,
            amount=Decimal("50.00"),
        )

        # Check balance.
        self.assertEqual(app.get_balance(account_id1), Decimal("150.00"))

        # Fail to withdraw funds - insufficient funds.
        with self.assertRaises(InsufficientFundsError):
            app.withdraw_funds(
                debit_account_id=account_id1,
                amount=Decimal("151.00"),
            )

        # Check balance - should be unchanged.
        self.assertEqual(app.get_balance(account_id1), Decimal("150.00"))

        # Create another account.
        account_id2 = app.open_account(
            full_name="Bob",
            email_address="bob@example.com",
        )

        # Transfer funds.
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

        # Close account.
        app.close_account(account_id1)

        # Fail to transfer funds - account closed.
        with self.assertRaises(AccountClosedError):
            app.transfer_funds(
                debit_account_id=account_id1,
                credit_account_id=account_id2,
                amount=Decimal("50.00"),
            )

        # Fail to transfer funds - account closed.
        with self.assertRaises(AccountClosedError):
            app.transfer_funds(
                debit_account_id=account_id2,
                credit_account_id=account_id1,
                amount=Decimal("50.00"),
            )

        # Fail to withdraw funds - account closed.
        with self.assertRaises(AccountClosedError):
            app.withdraw_funds(
                debit_account_id=account_id1,
                amount=Decimal("1.00"),
            )

        # Fail to deposit funds - account closed.
        with self.assertRaises(AccountClosedError):
            app.deposit_funds(
                credit_account_id=account_id1,
                amount=Decimal("1000.00"),
            )

        # Check balance - should be unchanged.
        self.assertEqual(app.get_balance(account_id1), Decimal("50.00"))

        # Check overdraft limit.
        self.assertEqual(
            app.get_overdraft_limit(account_id2),
            Decimal("0.00"),
        )

        # Set overdraft limit.
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

        # Check overdraft limit.
        self.assertEqual(
            app.get_overdraft_limit(account_id2),
            Decimal("500.00"),
        )

        # Withdraw funds.
        app.withdraw_funds(
            debit_account_id=account_id2,
            amount=Decimal("500.00"),
        )

        # Check balance - should be overdrawn.
        self.assertEqual(
            app.get_balance(account_id2),
            Decimal("-400.00"),
        )

        # Fail to withdraw funds - insufficient funds.
        with self.assertRaises(InsufficientFundsError):
            app.withdraw_funds(
                debit_account_id=account_id2,
                amount=Decimal("101.00"),
            )

        # Fail to set overdraft limit - account closed.
        with self.assertRaises(AccountClosedError):
            app.set_overdraft_limit(
                account_id=account_id1,
                overdraft_limit=Decimal("500.00"),
            )
