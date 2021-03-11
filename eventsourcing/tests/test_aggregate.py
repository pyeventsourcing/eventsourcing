import inspect
from dataclasses import _DataclassParams, dataclass
from datetime import datetime
from decimal import Decimal
from unittest.case import TestCase
from uuid import UUID, uuid4

from eventsourcing.domain import (
    TZINFO,
    Aggregate,
    AggregateCreated,
    AggregateEvent,
    VersionError,
    aggregate,
)


class TestMetaAggregate(TestCase):

    def test_aggregate_class_has_a_created_event_class(self):
        self.assertTrue(hasattr(Aggregate, "_created_event_class"))
        self.assertTrue(issubclass(Aggregate._created_event_class, AggregateCreated))
        self.assertEqual(Aggregate._created_event_class, Aggregate.Created)

    def test_aggregate_subclass_is_a_dataclass(self):
        # No dataclass decorator.
        class MyAggregate(Aggregate):
            pass

        self.assertTrue("__dataclass_params__" in MyAggregate.__dict__)
        self.assertIsInstance(MyAggregate.__dataclass_params__, _DataclassParams)
        self.assertFalse(MyAggregate.__dataclass_params__.frozen)

        # Has a dataclass decorator (helps IDE know what's going on).
        @dataclass
        class MyAggregate(Aggregate):
            pass

        self.assertTrue("__dataclass_params__" in MyAggregate.__dict__)
        self.assertIsInstance(MyAggregate.__dataclass_params__, _DataclassParams)
        self.assertFalse(MyAggregate.__dataclass_params__.frozen)

    def test_aggregate_subclass_gets_a_default_created_event_class(self):
        class MyAggregate(Aggregate):
            pass

        self.assertTrue(hasattr(MyAggregate, "_created_event_class"))
        self.assertTrue(issubclass(MyAggregate._created_event_class, AggregateCreated))
        self.assertEqual(MyAggregate._created_event_class, MyAggregate.Created)

    def test_aggregate_subclass_has_a_custom_created_event_class(self):
        class MyAggregate(Aggregate):
            class Started(AggregateCreated):
                pass

        self.assertTrue(hasattr(MyAggregate, "_created_event_class"))
        self.assertTrue(issubclass(MyAggregate._created_event_class, AggregateCreated))
        self.assertEqual(MyAggregate._created_event_class, MyAggregate.Started)

    def test_aggregate_subclass_has_a_custom_created_event_class_name(self):
        @dataclass
        class MyAggregate(Aggregate, created_event_name="Started"):
            pass

        a = MyAggregate()
        self.assertEqual(type(a.pending_events[0]).__name__, "Started")

        self.assertTrue(hasattr(MyAggregate, "_created_event_class"))
        created_event_cls = MyAggregate._created_event_class
        self.assertEqual(created_event_cls.__name__, "Started")
        self.assertTrue(created_event_cls.__qualname__.endswith("MyAggregate.Started"))
        self.assertTrue(issubclass(created_event_cls, AggregateCreated))
        self.assertEqual(created_event_cls, MyAggregate.Started)


class TestAggregateCreation(TestCase):
    def test_call_class_method_create(self):
        # Check the _create() method creates a new aggregate.
        before_created = datetime.now(tz=TZINFO)
        uuid = uuid4()
        a = Aggregate._create(
            event_class=AggregateCreated,
            id=uuid,
        )
        after_created = datetime.now(tz=TZINFO)
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(a.id, uuid)
        self.assertEqual(a.version, 1)
        self.assertEqual(a.created_on, a.modified_on)
        self.assertGreater(a.created_on, before_created)
        self.assertGreater(after_created, a.created_on)

    def test_call_base_class(self):
        before_created = datetime.now(tz=TZINFO)
        a = Aggregate()
        after_created = datetime.now(tz=TZINFO)
        self.assertIsInstance(a, Aggregate)
        self.assertIsInstance(a.id, UUID)
        self.assertIsInstance(a.version, int)
        self.assertEqual(a.version, 1)
        self.assertIsInstance(a.created_on, datetime)
        self.assertIsInstance(a.modified_on, datetime)
        self.assertEqual(a.created_on, a.modified_on)
        self.assertGreater(a.created_on, before_created)
        self.assertGreater(after_created, a.created_on)

        events = a.collect_events()
        self.assertIsInstance(events[0], AggregateCreated)
        self.assertEqual("Aggregate.Created", type(events[0]).__qualname__)

    def test_call_subclass_with_no_init(self):
        qualname = type(self).__qualname__
        prefix = f"{qualname}.test_call_subclass_with_no_init.<locals>."

        class MyAggregate(Aggregate):
            pass

        a = MyAggregate()
        self.assertIsInstance(a.id, UUID)
        self.assertIsInstance(a.version, int)
        self.assertEqual(a.version, 1)
        self.assertIsInstance(a.created_on, datetime)
        self.assertIsInstance(a.modified_on, datetime)

        events = a.collect_events()
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], AggregateCreated)
        self.assertEqual(f"{prefix}MyAggregate.Created", type(events[0]).__qualname__)

        # Do it again using @dataclass
        @dataclass  # ...this just makes the code completion work in the IDE.
        class MyAggregate(Aggregate):
            pass

        # Check the init method takes no args (except "self").
        init_params = inspect.signature(MyAggregate.__init__).parameters
        self.assertEqual(len(init_params), 1)
        self.assertEqual(list(init_params)[0], "self")

        #
        # Do it again with custom "created" event.
        @dataclass
        class MyAggregate(Aggregate):
            class Started(AggregateCreated):
                pass

        a = MyAggregate()
        self.assertIsInstance(a.id, UUID)
        self.assertIsInstance(a.version, int)
        self.assertIsInstance(a.created_on, datetime)
        self.assertIsInstance(a.modified_on, datetime)

        events = a.collect_events()
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], AggregateCreated)
        self.assertEqual(f"{prefix}MyAggregate.Started", type(events[0]).__qualname__)

    def test_call_subclass_with_init_that_has_no_args(self):
        qualname = type(self).__qualname__
        prefix = f"{qualname}.test_call_subclass_with_init_that_has_no_args.<locals>."

        class MyAggregate(Aggregate):
            def __init__(self):
                pass

        a = MyAggregate()
        self.assertIsInstance(a.id, UUID)
        self.assertIsInstance(a.version, int)
        self.assertIsInstance(a.created_on, datetime)
        self.assertIsInstance(a.modified_on, datetime)

        events = a.collect_events()
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], AggregateCreated)
        self.assertEqual(f"{prefix}MyAggregate.Created", type(events[0]).__qualname__)

        #
        # Do it again using @dataclass (makes no difference)...
        @dataclass  # ...this just makes the code completion work in the IDE.
        class MyAggregate(Aggregate):
            def __init__(self):
                pass

        # Check the init method takes no args (except "self").
        init_params = inspect.signature(MyAggregate.__init__).parameters
        self.assertEqual(len(init_params), 1)
        self.assertEqual(list(init_params)[0], "self")

        #
        # Do it again with custom "created" event.
        @dataclass
        class MyAggregate(Aggregate):
            class Started(AggregateCreated):
                pass

        a = MyAggregate()
        self.assertIsInstance(a.id, UUID)
        self.assertIsInstance(a.version, int)
        self.assertIsInstance(a.created_on, datetime)
        self.assertIsInstance(a.modified_on, datetime)

        events = a.collect_events()
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], AggregateCreated)
        self.assertEqual(f"{prefix}MyAggregate.Started", type(events[0]).__qualname__)

    def test_raises_when_create_args_mismatch_created_event(self):
        p = (
            "TestAggregateCreation"
            ".test_raises_when_create_args_mismatch_created_event"
            ".<locals>."
        )

        class BrokenAggregate(Aggregate):
            @classmethod
            def create(cls, name):
                return cls._create(event_class=cls.Created, id=uuid4(), name=name)

        with self.assertRaises(TypeError) as cm:
            BrokenAggregate.create("name")
        self.assertEqual(
            (
                f"Unable to construct 'aggregate created' event with class {p}"
                "BrokenAggregate.Created and keyword args {'name': 'name'}: "
                f"__init__() got an unexpected keyword argument 'name'"
            ),
            cm.exception.args[0],
        )

    def test_refuse_implicit_choice_of_alternative_created_events(self):
        # In case aggregates were created with old Created event,
        # there may need to be several defined. Then, when calling
        # aggregate class, require explicit statement of which to use.
        class MyAggregate(Aggregate):
            class Started(AggregateCreated):
                pass

            class Opened(AggregateCreated):
                pass

        with self.assertRaises(TypeError) as cm:
            MyAggregate()
        self.assertEqual(
            cm.exception.args[0],
            "attribute '_created_event_class' not set on class"
        )

        # Can still create an aggregate, by calling the _create() method.
        a = MyAggregate._create(MyAggregate.Opened)
        events = a.collect_events()
        self.assertIsInstance(events[0], MyAggregate.Opened)

        a = MyAggregate._create(MyAggregate.Started)
        events = a.collect_events()
        self.assertIsInstance(events[0], MyAggregate.Started)

        # Say which created event class to use on aggregate class.
        class MyAggregate(Aggregate):
            class Started(AggregateCreated):
                pass

            class Opened(AggregateCreated):
                pass

            _created_event_class = Started

        # Call class, and expect Started event will be used.
        a = MyAggregate()
        events = a.collect_events()
        self.assertIsInstance(events[0], MyAggregate.Started)


class TestSubsequentEvents(TestCase):

    def test_trigger_event(self):
        a = Aggregate()

        # Check the aggregate can trigger further events.
        a.trigger_event(AggregateEvent)
        self.assertLess(a.created_on, a.modified_on)

        pending = a.collect_events()
        self.assertEqual(len(pending), 2)
        self.assertIsInstance(pending[0], AggregateCreated)
        self.assertEqual(pending[0].originator_version, 1)
        self.assertIsInstance(pending[1], AggregateEvent)
        self.assertEqual(pending[1].originator_version, 2)

    def test_event_mutate_raises_version_error(self):
        a = Aggregate()

        # Try to mutate aggregate with an invalid domain event.
        event = AggregateEvent(
            originator_id=a.id,
            originator_version=a.version,  # NB not +1.
            timestamp=datetime.now(tz=TZINFO),
        )
        # Check raises "VersionError".
        with self.assertRaises(VersionError):
            event.mutate(a)

    def test_raises_when_triggering_event_with_mismatched_args(self):
        class MyAgg(Aggregate):
            @classmethod
            def create(cls):
                return cls._create(event_class=cls.Created, id=uuid4())

            class ValueUpdated(AggregateEvent):
                a: int

        a = MyAgg.create()

        with self.assertRaises(TypeError) as cm:
            a.trigger_event(MyAgg.ValueUpdated)
        self.assertTrue(
            cm.exception.args[0].startswith("Can't construct event"),
            cm.exception.args[0],
        )
        self.assertTrue(
            cm.exception.args[0].endswith(
                "__init__() missing 1 required positional argument: 'a'"
            ),
            cm.exception.args[0],
        )


class TestBankAccount(TestCase):
    def test_subclass_bank_account(self):
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
        with self.assertRaises(InsufficientFundsError):
            account.append_transaction(Decimal("-15.00"))

        # Increase the overdraft limit.
        account.set_overdraft_limit(Decimal("100.00"))

        # Debit the account.
        account.append_transaction(Decimal("-15.00"))

        # Check the balance.
        assert account.balance == Decimal("-10.00")

        # Close the account.
        account.close()

        # Fail to debit account (account closed).
        with self.assertRaises(AccountClosedError):
            account.append_transaction(Decimal("-15.00"))

        # Collect pending events.
        pending = account.collect_events()
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
        return cls._create(
            cls.Opened,
            id=uuid4(),
            full_name=full_name,
            email_address=email_address,
        )

    class Opened(AggregateCreated):
        full_name: str
        email_address: str

    def append_transaction(self, amount: Decimal) -> None:
        """
        Appends given amount as transaction on account.
        """
        self.check_account_is_not_closed()
        self.check_has_sufficient_funds(amount)
        self.trigger_event(
            self.TransactionAppended,
            amount=amount,
        )

    def check_account_is_not_closed(self) -> None:
        if self.is_closed:
            raise AccountClosedError({"account_id": self.id})

    def check_has_sufficient_funds(self, amount: Decimal) -> None:
        if self.balance + amount < -self.overdraft_limit:
            raise InsufficientFundsError({"account_id": self.id})

    class TransactionAppended(AggregateEvent):
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
        self.trigger_event(
            self.OverdraftLimitSet,
            overdraft_limit=overdraft_limit,
        )

    class OverdraftLimitSet(AggregateEvent):
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
        self.trigger_event(self.Closed)

    class Closed(AggregateEvent):
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
