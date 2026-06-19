from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Any, ClassVar
from unittest import TestCase
from uuid import UUID, uuid4

from eventsourcing.application import Application
from eventsourcing.domain import (
    Aggregate,
    AggregateCreated,
    AggregateEvent,
    BaseAggregate,
    CanSnapshotAggregate,
    MetaDomainEvent,
    MutableOrImmutableAggregate,
    Snapshot,
    datetime_now_with_tzinfo,
    get_metadata_from_context,
)
from eventsourcing.tests.application import BankAccounts
from eventsourcing.tests.domain import BankAccount

if TYPE_CHECKING:
    from datetime import datetime


class BankAccountsWithAutomaticSnapshotting(BankAccounts):
    is_snapshotting_enabled = False
    snapshotting_intervals: ClassVar[
        dict[type[MutableOrImmutableAggregate[UUID]], int]
    ] = {BankAccount: 5}


class TestApplicationWithAutomaticSnapshotting(TestCase):
    def test_snapshotting_intervals(self) -> None:
        app = BankAccountsWithAutomaticSnapshotting()

        # Check snapshotting is enabled by setting snapshotting_intervals only.
        self.assertTrue(app.snapshots)

        # Open an account.
        account_id = app.open_account("Alice", "alice@example.com")

        # Check there are no snapshots.
        assert app.snapshots is not None  # for mypy
        snapshots = list(app.snapshots.get(account_id))
        self.assertEqual(len(snapshots), 0)

        # Trigger twelve more events.
        for _ in range(12):
            app.credit_account(account_id, Decimal("10.00"))

        # Check the account is at version 13.
        account = app.get_account(account_id)
        self.assertEqual(account.version, 13)

        # Check snapshots have been taken at regular intervals.
        snapshots = list(app.snapshots.get(account_id))
        self.assertEqual(len(snapshots), 2)
        self.assertEqual(snapshots[0].originator_version, 5)
        self.assertEqual(snapshots[1].originator_version, 10)

        # Check another type of aggregate is not snapshotted.
        aggregate = Aggregate()
        for _ in range(10):
            aggregate.trigger_event(Aggregate.Event)
        app.save(aggregate)

        # Check snapshots have not been taken at regular intervals.
        snapshots = list(app.snapshots.get(aggregate.id))
        self.assertEqual(len(snapshots), 0)

    def test_raises_when_snapshot_not_defined(self) -> None:
        class MyAggregate1(BaseAggregate[UUID]):
            class Event(AggregateEvent):
                pass

            class Created(Event, AggregateCreated):
                pass

            @staticmethod
            def create_id() -> UUID:
                return uuid4()

        env = {"IS_SNAPSHOTTING_ENABLED": "y"}

        a1 = MyAggregate1()
        app = Application[UUID](env=env)
        app.save(a1)

        with self.assertRaises(AssertionError) as cm1:
            app.take_snapshot(a1.id)

        self.assertIn(
            "Neither application nor aggregate have a snapshot class.",
            str(cm1.exception),
        )

        # This is okay.
        class MyApplication1(Application[UUID]):
            snapshot_class = Snapshot

        app1 = MyApplication1(env=env)
        a1 = MyAggregate1()
        app1.save(a1)
        app1.take_snapshot(a1.id)

        # This is also okay.
        class MyAggregate2(MyAggregate1):
            Snapshot = Snapshot

        a2 = MyAggregate2()
        app.save(a2)
        app.take_snapshot(a2.id)

        # This is not okay - int does not implement snapshot protocol.
        class MyApplication2(Application[UUID]):
            snapshot_class = int  # type: ignore[assignment]

        app2 = MyApplication2(env=env)
        a1 = MyAggregate1()
        app2.save(a1)
        with self.assertRaises(AttributeError) as cm2:
            app2.take_snapshot(a1.id)

        self.assertIn(
            "type object 'int' has no attribute 'take'",
            str(cm2.exception),
        )

        # This is also not okay - application uses string aggregate IDs.
        class MyApplication3(Application[str]):
            snapshot_class = Snapshot  # type: ignore[assignment]

        app3 = MyApplication3(env=env)
        a1 = MyAggregate1()
        app3.save(a1)  # type: ignore[arg-type]
        app3.take_snapshot(a1.id)  # type: ignore[arg-type]
        # ...but it works!

        # This is also not okay - snapshot uses string aggregate IDs.

        @dataclass(frozen=True)
        class DomainEvent(metaclass=MetaDomainEvent):
            originator_id: str
            originator_version: int
            timestamp: datetime = field(default_factory=datetime_now_with_tzinfo)
            metadata: dict[str, str] = field(default_factory=get_metadata_from_context)
            event_id: UUID = field(default_factory=uuid4)

            def __post_init__(self) -> None:
                assert isinstance(self.originator_id, str), "Not a string"

        @dataclass(frozen=True, kw_only=True)
        class StrSnapshot(DomainEvent, CanSnapshotAggregate[str]):
            topic: str
            state: dict[str, Any]

        class MyApplication4(Application[str]):
            snapshot_class = StrSnapshot

        app4 = MyApplication4(env=env)
        a1 = MyAggregate1()
        app4.save(a1)  # type: ignore[arg-type]
        with self.assertRaises(AssertionError) as cm3:
            app4.take_snapshot(a1.id)  # type: ignore[arg-type]

        self.assertIn("Not a string", str(cm3.exception))
