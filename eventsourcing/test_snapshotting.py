from decimal import Decimal
from unittest import TestCase

from eventsourcing.eventmapper import (
    DatetimeAsISO,
    DecimalAsStr,
    Mapper,
    Transcoder,
    UUIDAsHex,
)
from eventsourcing.eventstore import EventStore
from eventsourcing.snapshotting import Snapshot
from eventsourcing.sqliterecorders import (
    SQLiteDatabase,
    SQLiteAggregateRecorder,
)
from eventsourcing.test_aggregate import BankAccount


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

        transcoder = Transcoder()
        transcoder.register(UUIDAsHex())
        transcoder.register(DecimalAsStr())
        transcoder.register(DatetimeAsISO())
        snapshot_store = EventStore(
            mapper=Mapper(transcoder=transcoder),
            recorder=SQLiteAggregateRecorder(
                SQLiteDatabase(":memory:"),
                table_name="snapshots",
            ),
        )
        snapshot_store.recorder.create_table()

        # Clear pending events.
        account._collect_()

        # Take a snapshot.
        snapshot = Snapshot.take(account)

        self.assertNotIn('pending_events', snapshot.state)

        # Store snapshot.
        snapshot_store.put([snapshot])

        # Get snapshot.
        snapshots = snapshot_store.get(
            account.uuid, desc=True, limit=1
        )
        snapshot = next(snapshots)
        assert isinstance(snapshot, Snapshot)

        # Reconstruct the bank account.
        copy = snapshot.mutate()
        assert isinstance(copy, BankAccount)

        # Check copy has correct attribute values.
        assert copy.uuid == account.uuid
        assert copy.balance == Decimal("65.00")
