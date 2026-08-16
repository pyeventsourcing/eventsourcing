from __future__ import annotations

from decimal import Decimal
from typing import Self

from pydantic import BaseModel

from eventsourcing.decorator import triggers
from eventsourcing.pydantic import (
    Aggregate,
    AggregateSnapshot,
    AggregateState,
    Decision,
)


class EmailAddress(BaseModel):
    address: str


class BankAccountState(AggregateState):
    full_name: str
    email_address: EmailAddress
    balance: Decimal
    overdraft_limit: Decimal
    is_closed: bool


class BankAccountWithPydantic(Aggregate):
    """Aggregate root for bank accounts."""

    class Opened(Decision):
        full_name: str
        email_address: EmailAddress

    class TransactionAppended(Decision):
        amount: Decimal

    class OverdraftLimitSet(Decision):
        overdraft_limit: Decimal

    class Closed(Decision):
        pass

    class Snapshot(AggregateSnapshot):
        state: BankAccountState

    @triggers(Opened)
    def __init__(self, full_name: str, email_address: EmailAddress):
        self.full_name = full_name
        self.email_address = email_address
        self.balance = Decimal("0.00")
        self.overdraft_limit = Decimal("0.00")
        self.is_closed = False

    @classmethod
    def open(cls, full_name: str, email_address: str) -> Self:
        """Creates new bank account object."""
        return cls._create(
            full_name=full_name,
            email_address=EmailAddress(address=email_address),
        )

    @triggers(TransactionAppended)
    def append_transaction(self, amount: Decimal) -> None:
        """Appends given amount as transaction on account."""
        self.check_account_is_not_closed()
        self.check_has_sufficient_funds(amount)
        self.balance += amount

    def check_account_is_not_closed(self) -> None:
        if self.is_closed:
            raise AccountClosedError({"account_id": self.id})

    def check_has_sufficient_funds(self, amount: Decimal) -> None:
        if self.balance + amount < -self.overdraft_limit:
            raise InsufficientFundsError({"account_id": self.id})

    @triggers(OverdraftLimitSet)
    def set_overdraft_limit(self, overdraft_limit: Decimal) -> None:
        """Sets the overdraft limit."""
        # Check the limit is not a negative value.
        assert overdraft_limit >= Decimal("0.00")
        self.check_account_is_not_closed()
        self.overdraft_limit = overdraft_limit

    def close(self) -> None:
        """Closes the bank account."""
        self.is_closed = True


class AccountClosedError(Exception):
    """Raised when attempting to operate a closed account."""


class InsufficientFundsError(Exception):
    """Raised when attempting to go past overdraft limit."""
