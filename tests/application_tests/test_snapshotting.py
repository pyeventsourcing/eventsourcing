from decimal import Decimal
from unittest import TestCase

from eventsourcing.domain_new import AggregateEvent
from eventsourcing.persistence import (
    AggregateEventMapper,
    EventStore,
)
from eventsourcing.pydantic.immutable import PydanticDecision
from eventsourcing.pydantic.transcoder import PydanticTranscoder
from eventsourcing.sqlite import SQLiteAggregateRecorder, SQLiteDatastore
from eventsourcing.tests.bank_account_with_pydantic import BankAccountWithPydantic


class TestSnapshotting(TestCase):
    def test_snapshotting(self) -> None:
        # Open an account.
        account = BankAccountWithPydantic.open(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Credit the account.
        account.append_transaction(Decimal("10.00"))
        account.append_transaction(Decimal("25.00"))
        account.append_transaction(Decimal("30.00"))

        transcoder = PydanticTranscoder()

        recorder = SQLiteAggregateRecorder(
            SQLiteDatastore(":memory:"),
            events_table_name="snapshots",
        )
        snapshot_store = EventStore[PydanticDecision](
            mapper=AggregateEventMapper(transcoder=transcoder),
            recorder=recorder,
        )
        recorder.create_table()

        # Clear pending events.
        account.collect_events()

        # Take a snapshot.
        # Store snapshot.
        snapshot_store.put(
            [
                AggregateEvent(
                    decision=BankAccountWithPydantic.Snapshot.take(account),
                    originator_id=account.id,
                    originator_version=account.version,
                )
            ]
        )

        # Get snapshot.
        snapshots = snapshot_store.get(account.id, desc=True, limit=1)
        snapshot = next(snapshots)
        assert isinstance(snapshot, AggregateEvent)
        assert isinstance(snapshot.decision, BankAccountWithPydantic.Snapshot)

        # Reconstruct the bank account.
        copy = snapshot.mutate(BankAccountWithPydantic.__new__(BankAccountWithPydantic))
        assert isinstance(copy, BankAccountWithPydantic)

        # Check copy has correct attribute values.
        assert copy.id == account.id
        assert copy.balance == Decimal("65.00")
