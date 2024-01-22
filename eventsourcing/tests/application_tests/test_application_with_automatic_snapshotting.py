from __future__ import annotations

from decimal import Decimal
from typing import ClassVar, Dict, Type
from unittest import TestCase

from eventsourcing.domain import Aggregate, MutableOrImmutableAggregate
from eventsourcing.tests.application import BankAccounts
from eventsourcing.tests.domain import BankAccount


class BankAccountsWithAutomaticSnapshotting(BankAccounts):
    is_snapshotting_enabled = False
    snapshotting_intervals: ClassVar[
        Dict[Type[MutableOrImmutableAggregate], int] | None
    ] = {BankAccount: 5}


class TestApplicationWithAutomaticSnapshotting(TestCase):
    def test(self):
        app = BankAccountsWithAutomaticSnapshotting()

        # Check snapshotting is enabled by setting snapshotting_intervals only.
        self.assertTrue(app.snapshots)

        # Open an account.
        account_id = app.open_account("Alice", "alice@example.com")

        # Check there are no snapshots.
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
