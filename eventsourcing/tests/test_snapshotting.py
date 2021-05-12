from decimal import Decimal
from unittest import TestCase

from eventsourcing.domain import Snapshot
from eventsourcing.persistence import (
    DatetimeAsISO,
    DecimalAsStr,
    EventStore,
    JSONTranscoder,
    Mapper,
    UUIDAsHex,
)
from eventsourcing.sqlite import SQLiteAggregateRecorder, SQLiteDatastore
from eventsourcing.tests.test_aggregate import BankAccount
from eventsourcing.tests.test_application import EmailAddressAsStr


class TestSnapshotting(TestCase):
    def test(self):
        # Open an account.
        account = BankAccount.open(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Credit the account.
        account.append_transaction(Decimal("10.00"))
        account.append_transaction(Decimal("25.00"))
        account.append_transaction(Decimal("30.00"))

        transcoder = JSONTranscoder()
        transcoder.register(UUIDAsHex())
        transcoder.register(DecimalAsStr())
        transcoder.register(DatetimeAsISO())
        transcoder.register(EmailAddressAsStr())

        snapshot_store = EventStore(
            mapper=Mapper(transcoder=transcoder),
            recorder=SQLiteAggregateRecorder(
                SQLiteDatastore(":memory:"),
                events_table_name="snapshots",
            ),
        )
        snapshot_store.recorder.create_table()

        # Clear pending events.
        account.collect_events()

        # Take a snapshot.
        snapshot = Snapshot.take(account)

        self.assertNotIn("pending_events", snapshot.state)

        # Store snapshot.
        snapshot_store.put([snapshot])

        # Get snapshot.
        snapshots = snapshot_store.get(account.id, desc=True, limit=1)
        snapshot = next(snapshots)
        assert isinstance(snapshot, Snapshot)

        # Reconstruct the bank account.
        copy = snapshot.mutate()
        assert isinstance(copy, BankAccount)

        # Check copy has correct attribute values.
        assert copy.id == account.id
        assert copy.balance == Decimal("65.00")
