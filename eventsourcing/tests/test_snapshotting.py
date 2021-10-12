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
from eventsourcing.tests.test_application_with_popo import EmailAddressAsStr


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

        recorder = SQLiteAggregateRecorder(
            SQLiteDatastore(":memory:"),
            events_table_name="snapshots",
        )
        recorder.create_table()

        snapshot_store: EventStore[Snapshot] = EventStore(
            mapper=Mapper(transcoder=transcoder),
            recorder=recorder,
        )

        # Clear pending events.
        account.collect_events()

        # Take a snapshot.
        snapshot = Snapshot.take(account)

        self.assertNotIn("pending_events", snapshot.state)

        # Store snapshot.
        snapshot_store.put([snapshot])

        # Get snapshot.
        snapshot_copy = snapshot_store.get(account.id, desc=True, limit=1)[0]

        # Reconstruct the bank account.
        account_copy: BankAccount = snapshot_copy.mutate()
        assert isinstance(account_copy, BankAccount)

        # Check copy has correct attribute values.
        assert account_copy.id == account.id
        assert account_copy.balance == Decimal("65.00")
