from unittest.case import TestCase

from decimal import Decimal

from eventsourcing.aggregate import (
    AccountClosedError,
    BankAccount,
    InsufficientFundsError,
)


class TestAggregate(TestCase):
    def test(self):

        # Open an account.
        account: BankAccount = BankAccount.open(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Check the created_on.
        assert account.created_on == account.modified_on

        # Check the initial balance.
        assert account.balance == 0

        # Credit the account.
        account.append_transaction(Decimal("10.00"))

        # Check the modified_on time was updated.
        assert account.created_on < account.modified_on

        # Check the balance.
        assert account.balance == Decimal("10.00")

        # Credit the account again.
        account.append_transaction(Decimal("10.00"))

        # Check the balance.
        assert account.balance == Decimal("20.00")

        # Debit the account.
        account.append_transaction(Decimal("-15.00"))

        # Check the balance.
        assert account.balance == Decimal("5.00")

        # Fail to debit account (insufficient funds).
        try:
            account.append_transaction(Decimal("-15.00"))
        except InsufficientFundsError:
            pass
        else:
            raise Exception(
                "Insufficient funds error not raised"
            )

        # Increase the overdraft limit.
        account.set_overdraft_limit(Decimal("100.00"))

        # Debit the account.
        account.append_transaction(Decimal("-15.00"))

        # Check the balance.
        assert account.balance == Decimal("-10.00")

        # Close the account.
        account.close()

        # Fail to debit account (account closed).
        try:
            account.append_transaction(Decimal("-15.00"))
        except AccountClosedError:
            pass
        else:
            raise Exception(
                "Account closed error not raised"
            )

        # Collect pending events.
        pending = account._collect_()
        assert len(pending) == 7
