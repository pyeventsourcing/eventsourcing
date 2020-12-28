from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Type
from uuid import UUID, uuid4

from eventsourcing.domainevent import DomainEvent
from eventsourcing.utils import get_topic, resolve_topic


class Aggregate:
    """
    Base class for aggregate roots.
    """

    class Event(DomainEvent):
        """
        Base domain event class for aggregates.
        """

        def mutate(
            self, obj: Optional["Aggregate"]
        ) -> Optional["Aggregate"]:
            """
            Changes the state of the aggregate
            according to domain event attributes.
            """
            # Check event is next in its sequence.
            # Use counting to follow the sequence.
            assert isinstance(obj, Aggregate)
            next_version = obj.version + 1
            if self.originator_version != next_version:
                raise obj.VersionError(
                    self.originator_version, next_version
                )
            # Update the aggregate version.
            obj.version = next_version
            # Update the modified time.
            obj.modified_on = self.timestamp
            self.apply(obj)
            return obj

        def apply(self, obj) -> None:
            pass

    class VersionError(Exception):
        pass

    def __init__(
        self, id: UUID, version: int, timestamp: datetime
    ):
        """
        Aggregate is constructed with an 'id'
        and a 'version'. The 'pending_events'
        is also initialised as an empty list.
        """
        self.id = id
        self.version = version
        self.created_on = timestamp
        self.modified_on = timestamp
        self._pending_events_: List[Aggregate.Event] = []

    @classmethod
    def _create_(
        cls,
        event_class: Type["Aggregate.Created"],
        id: UUID,
        **kwargs,
    ):
        """
        Factory method to construct a new
        aggregate object instance.
        """
        # Construct the domain event class,
        # with an ID and version, and the
        # a topic for the aggregate class.
        event = event_class(  # type: ignore
            originator_id=id,
            originator_version=1,
            originator_topic=get_topic(cls),
            timestamp=datetime.now(),
            **kwargs,
        )
        # Construct the aggregate object.
        aggregate = event.mutate(None)
        # Append the domain event to pending list.
        aggregate._pending_events_.append(event)
        # Return the aggregate.
        return aggregate

    class Created(Event):
        """
        Domain event for when aggregate is created.
        """

        originator_topic: str

        def mutate(
            self, obj: Optional["Aggregate"]
        ) -> "Aggregate":
            """
            Constructs aggregate instance defined
            by domain event object attributes.
            """
            # Copy the event attributes.
            kwargs = self.__dict__.copy()
            # Separate the id and version.
            id = kwargs.pop("originator_id")
            version = kwargs.pop("originator_version")
            # Get the aggregate root class from topic.
            aggregate_class = resolve_topic(
                kwargs.pop("originator_topic")
            )
            # Construct and return aggregate object.
            return aggregate_class(
                id=id, version=version, **kwargs
            )

    def _trigger_(
        self,
        event_class: Type["Aggregate.Event"],
        **kwargs,
    ) -> None:
        """
        Triggers domain event of given type,
        extending the sequence of domain
        events for this aggregate object.
        """
        # Construct the domain event as the
        # next in the aggregate's sequence.
        # Use counting to generate the sequence.
        next_version = self.version + 1
        try:
            event = event_class(  # type: ignore
                originator_id=self.id,
                originator_version=next_version,
                timestamp=datetime.now(),
                **kwargs,
            )
        except AttributeError:
            raise
        # Mutate aggregate with domain event.
        event.mutate(self)
        # Append the domain event to pending list.
        self._pending_events_.append(event)

    def _collect_(self) -> List[Event]:
        """
        Collects pending events.
        """
        collected = []
        while self._pending_events_:
            collected.append(self._pending_events_.pop(0))
        return collected


class BankAccount(Aggregate):
    """
    Aggregate root for bank accounts.
    """

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

    def set_overdraft_limit(
        self, overdraft_limit: Decimal
    ) -> None:
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
