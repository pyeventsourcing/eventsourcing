from decimal import Decimal
from uuid import UUID, uuid4

from eventsourcing.aggregate import Aggregate


class TransactionError(Exception):
    pass
    # def __eq__(self, other):
    #     return self.args == other.args and type(
    #         self
    #     ) == type(other)


class AccountClosedError(TransactionError):
    pass


class InsufficientFundsError(TransactionError):
    pass


class BankAccount(Aggregate):
    def __init__(
        self, full_name: str, email_address: str, **kwargs
    ):
        super().__init__(**kwargs)
        self.full_name = full_name
        self.email_address = email_address
        self.balance = Decimal("0.00")
        self.overdraft_limit = Decimal("0.00")
        self.is_closed = False

    @classmethod
    def open(
        cls, full_name: str, email_address: str
    ) -> "BankAccount":
        return super()._create_(
            cls.Opened,
            id=uuid4(),
            full_name=full_name,
            email_address=email_address,
        )

    class Opened(Aggregate.Created):
        full_name: str
        email_address: str

    def append_transaction(
        self, amount: Decimal, transaction_id: UUID = None
    ) -> None:
        self.check_account_is_not_closed()
        self.check_has_sufficient_funds(amount)
        self._trigger_(
            self.TransactionAppended,
            amount=amount,
            transaction_id=transaction_id,
        )

    def check_account_is_not_closed(self) -> None:
        if self.is_closed:
            raise AccountClosedError(
                {"account_id": self.id}
            )

    def check_has_sufficient_funds(
        self, amount: Decimal
    ) -> None:
        if self.balance + amount < -self.overdraft_limit:
            raise InsufficientFundsError(
                {"account_id": self.id}
            )

    class TransactionAppended(Aggregate.Event):
        amount: Decimal
        transaction_id: UUID

        def apply(self, obj: "BankAccount") -> None:
            obj.balance += self.amount

    def set_overdraft_limit(
        self, overdraft_limit: Decimal
    ) -> None:
        assert overdraft_limit > Decimal("0.00")
        self.check_account_is_not_closed()
        self._trigger_(
            self.OverdraftLimitSet,
            overdraft_limit=overdraft_limit,
        )

    class OverdraftLimitSet(Aggregate.Event):
        overdraft_limit: Decimal

        def apply(self, obj: "BankAccount") -> None:
            obj.overdraft_limit = self.overdraft_limit

    def close(self):
        self._trigger_(self.Closed)

    class Closed(Aggregate.Event):
        def apply(self, obj: "BankAccount") -> None:
            obj.is_closed = True

    # def record_error(
    #     self, error: Exception, transaction_id=None
    # ):
    #     self._trigger_(
    #         self.ErrorRecorded,
    #         error=error,
    #         transaction_id=transaction_id,
    #     )
    #
    # class ErrorRecorded(Aggregate.Event):
    #     @property
    #     def error(self):
    #         return self.__dict__["error"]
