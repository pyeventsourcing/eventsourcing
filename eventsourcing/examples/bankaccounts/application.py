from __future__ import annotations

from typing import TYPE_CHECKING

from eventsourcing.application import AggregateNotFoundError, Application
from eventsourcing.examples.bankaccounts.domainmodel import BankAccount

if TYPE_CHECKING:  # pragma: nocover
    from decimal import Decimal
    from uuid import UUID


class BankAccounts(Application):
    def open_account(self, full_name: str, email_address: str) -> UUID:
        account = BankAccount(
            full_name=full_name,
            email_address=email_address,
        )
        self.save(account)
        return account.id

    def get_account(self, account_id: UUID) -> BankAccount:
        try:
            return self.repository.get(account_id)
        except AggregateNotFoundError:
            raise AccountNotFoundError(account_id) from None

    def get_balance(self, account_id: UUID) -> Decimal:
        account = self.get_account(account_id)
        return account.balance

    def deposit_funds(self, credit_account_id: UUID, amount: Decimal) -> None:
        account = self.get_account(credit_account_id)
        account.credit(amount)
        self.save(account)

    def withdraw_funds(self, debit_account_id: UUID, amount: Decimal) -> None:
        account = self.get_account(debit_account_id)
        account.debit(amount)
        self.save(account)

    def transfer_funds(
        self,
        debit_account_id: UUID,
        credit_account_id: UUID,
        amount: Decimal,
    ) -> None:
        debit_account = self.get_account(debit_account_id)
        credit_account = self.get_account(credit_account_id)
        debit_account.debit(amount)
        credit_account.credit(amount)
        self.save(debit_account, credit_account)

    def set_overdraft_limit(self, account_id: UUID, overdraft_limit: Decimal) -> None:
        account = self.get_account(account_id)
        account.set_overdraft_limit(overdraft_limit)
        self.save(account)

    def get_overdraft_limit(self, account_id: UUID) -> Decimal:
        account = self.get_account(account_id)
        return account.overdraft_limit

    def close_account(self, account_id: UUID) -> None:
        account = self.get_account(account_id)
        account.close()
        self.save(account)


class AccountNotFoundError(Exception):
    pass
