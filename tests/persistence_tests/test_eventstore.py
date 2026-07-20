from decimal import Decimal
from unittest.case import TestCase

from eventsourcing.domain_new import AggregateEvent
from eventsourcing.persistence import (
    AggregateEventMapper,
    EventStore,
)
from eventsourcing.pydantic.immutable import PydanticDecision
from eventsourcing.pydantic.transcoder import PydanticTranscoder
from eventsourcing.sqlite import SQLiteAggregateRecorder, SQLiteDatastore
from eventsourcing.tests.bank_account_with_pydantic import BankAccountWithPydantic


class TestEventStore(TestCase):
    def test(self) -> None:
        # Open an account.
        account = BankAccountWithPydantic.open(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Credit the account.
        account.append_transaction(Decimal("10.00"))
        account.append_transaction(Decimal("25.00"))
        account.append_transaction(Decimal("30.00"))

        # Collect pending events.
        pending = account.collect_events()

        # Construct event store.
        recorder = SQLiteAggregateRecorder(
            SQLiteDatastore(":memory:", originator_id_type="text")
        )
        event_store = EventStore[PydanticDecision](
            mapper=AggregateEventMapper(PydanticTranscoder()),
            recorder=recorder,
        )
        recorder.create_table()

        # Get last event.
        stored_events = event_store.get(account.id, desc=True, limit=1)
        self.assertEqual(list(stored_events), [])

        # Store pending events.
        event_store.put(pending)

        # Get domain events.
        events = event_store.get(account.id)

        # Reconstruct the bank account.
        copy: BankAccountWithPydantic | None = BankAccountWithPydantic.__new__(
            BankAccountWithPydantic
        )
        for event in events:
            assert isinstance(event, AggregateEvent)
            assert isinstance(event.decision, PydanticDecision)
            copy = event.mutate(copy)

        # Check copy has correct attribute values.
        assert copy is not None
        self.assertEqual(copy.id, account.id)
        self.assertEqual(copy.balance, Decimal("65.00"))

        # Get last event.
        events_tuple = tuple(event_store.get(account.id, desc=True, limit=1))
        self.assertEqual(len(events_tuple), 1)
        last_event = events_tuple[0]

        self.assertEqual(last_event.originator_id, account.id)
        assert type(last_event.decision) is BankAccountWithPydantic.TransactionAppended
