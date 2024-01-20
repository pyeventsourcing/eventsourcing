from __future__ import annotations

from decimal import Decimal

from eventsourcing.domain import Aggregate, event


class BankAccount(Aggregate):
    @event("Opened")
    def __init__(self, full_name: str, email_address: str):
        self.full_name = full_name
        self.email_address = email_address
        self.balance = Decimal("0.00")
        self.overdraft_limit = Decimal("0.00")
        self.is_closed = False

    @event("Credited")
    def credit(self, amount: Decimal) -> None:
        self.check_account_is_not_closed()
        self.balance += amount

    @event("Debited")
    def debit(self, amount: Decimal) -> None:
        self.check_account_is_not_closed()
        self.check_has_sufficient_funds(amount)
        self.balance -= amount

    @event("OverdraftLimitSet")
    def set_overdraft_limit(self, overdraft_limit: Decimal) -> None:
        assert overdraft_limit > Decimal("0.00")
        self.check_account_is_not_closed()
        self.overdraft_limit = overdraft_limit

    @event("Closed")
    def close(self) -> None:
        self.is_closed = True

    def check_account_is_not_closed(self) -> None:
        if self.is_closed:
            raise AccountClosedError({"account_id": self.id})

    def check_has_sufficient_funds(self, amount: Decimal) -> None:
        if self.balance - amount < -self.overdraft_limit:
            raise InsufficientFundsError({"account_id": self.id})


class TransactionError(Exception):
    pass


class AccountClosedError(TransactionError):
    pass


class InsufficientFundsError(TransactionError):
    pass
