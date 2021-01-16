from datetime import datetime
from decimal import Decimal
from unittest.case import TestCase
from uuid import uuid4

from eventsourcing.domain import Aggregate, TZINFO, VersionError


class TestAggregate(TestCase):
    def test_aggregate_base_class(self):
        # Check the _create_() method creates a new aggregate.
        before_created = datetime.now(tz=TZINFO)
        uuid = uuid4()
        a = Aggregate._create_(
            event_class=Aggregate.Created,
            id=uuid,
        )
        after_created = datetime.now(tz=TZINFO)
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(a.id, uuid)
        self.assertEqual(a._version_, 1)
        self.assertEqual(a._created_on_, a._modified_on_)
        self.assertGreater(a._created_on_, before_created)
        self.assertGreater(after_created, a._created_on_)

        # Check the aggregate can trigger further events.
        a._trigger_(Aggregate.Event)
        self.assertLess(a._created_on_, a._modified_on_)

        pending = a._collect_()
        self.assertEqual(len(pending), 2)
        self.assertIsInstance(pending[0], Aggregate.Created)
        self.assertEqual(pending[0].originator_version, 1)
        self.assertIsInstance(pending[1], Aggregate.Event)
        self.assertEqual(pending[1].originator_version, 2)

        # Try to mutate aggregate with an invalid domain event.
        next_version = a._version_
        event = Aggregate.Event(
            originator_id=a.id,
            originator_version=next_version,
            timestamp=datetime.now(tz=TZINFO),
        )
        # Check raises "VersionError".
        with self.assertRaises(VersionError):
            event.mutate(a)

    def test_subclass_bank_account(self):

        # Open an account.
        account: BankAccount = BankAccount.open(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Check the _created_on_.
        assert account._created_on_ == account._modified_on_

        # Check the initial balance.
        assert account.balance == 0

        # Credit the account.
        account.append_transaction(Decimal("10.00"))

        # Check the _modified_on_ time was updated.
        assert account._created_on_ < account._modified_on_

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
            raise Exception("Insufficient funds error not raised")

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
            raise Exception("Account closed error not raised")

        # Collect pending events.
        pending = account._collect_()
        assert len(pending) == 7


class BankAccount(Aggregate):
    """
    Aggregate root for bank accounts.
    """

    def __init__(self, full_name: str, email_address: str, **kwargs):
        super().__init__(**kwargs)
        self.full_name = full_name
        self.email_address = email_address
        self.balance = Decimal("0.00")
        self.overdraft_limit = Decimal("0.00")
        self.is_closed = False

    @classmethod
    def open(cls, full_name: str, email_address: str) -> "BankAccount":
        """
        Creates new bank account object.
        """
        return super()._create_(
            cls.Opened,
            id=uuid4(),
            full_name=full_name,
            email_address=email_address,
        )

    class Opened(Aggregate.Created):
        full_name: str
        email_address: str

    def append_transaction(self, amount: Decimal) -> None:
        """
        Appends given amount as transaction on account.
        """
        self.check_account_is_not_closed()
        self.check_has_sufficient_funds(amount)
        self._trigger_(
            self.TransactionAppended,
            amount=amount,
        )

    def check_account_is_not_closed(self) -> None:
        if self.is_closed:
            raise AccountClosedError({"account_id": self.id})

    def check_has_sufficient_funds(self, amount: Decimal) -> None:
        if self.balance + amount < -self.overdraft_limit:
            raise InsufficientFundsError({"account_id": self.id})

    class TransactionAppended(Aggregate.Event):
        """
        Domain event for when transaction
        is appended to bank account.
        """

        amount: Decimal

        def apply(self, account: "BankAccount") -> None:
            """
            Increments the account balance.
            """
            account.balance += self.amount

    def set_overdraft_limit(self, overdraft_limit: Decimal) -> None:
        """
        Sets the overdraft limit.
        """
        # Check the limit is not a negative value.
        assert overdraft_limit >= Decimal("0.00")
        self.check_account_is_not_closed()
        self._trigger_(
            self.OverdraftLimitSet,
            overdraft_limit=overdraft_limit,
        )

    class OverdraftLimitSet(Aggregate.Event):
        """
        Domain event for when overdraft
        limit is set.
        """

        overdraft_limit: Decimal

        def apply(self, account: "BankAccount"):
            account.overdraft_limit = self.overdraft_limit

    def close(self) -> None:
        """
        Closes the bank account.
        """
        self._trigger_(self.Closed)

    class Closed(Aggregate.Event):
        """
        Domain event for when account is closed.
        """

        def apply(self, account: "BankAccount"):
            account.is_closed = True


class AccountClosedError(Exception):
    """
    Raised when attempting to operate a closed account.
    """


class InsufficientFundsError(Exception):
    """
    Raised when attempting to go past overdraft limit.
    """
