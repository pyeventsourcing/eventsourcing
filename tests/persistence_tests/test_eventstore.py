from decimal import Decimal
from unittest.case import TestCase
from uuid import UUID

from eventsourcing.domain import CanMutateProtocol
from eventsourcing.persistence import (
    DataclassMapper,
    DatetimeAsISO,
    DecimalAsStr,
    EventStore,
    JSONTranscoder,
    UUIDAsHex,
)
from eventsourcing.sqlite import SQLiteAggregateRecorder, SQLiteDatastore
from eventsourcing.tests.application import EmailAddressAsStr
from eventsourcing.tests.domain import BankAccount


class TestEventStore(TestCase):
    def test(self) -> None:
        # Open an account.
        account = BankAccount.open(
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
        transcoder = JSONTranscoder()
        transcoder.register(UUIDAsHex())
        transcoder.register(DecimalAsStr())
        transcoder.register(DatetimeAsISO())
        transcoder.register(EmailAddressAsStr())
        recorder = SQLiteAggregateRecorder(SQLiteDatastore(":memory:"))
        event_store = EventStore[UUID](
            mapper=DataclassMapper(transcoder),
            recorder=recorder,
        )
        recorder.create_table()

        # Get last event.
        stored_events = event_store.get(account.id, desc=True, limit=1)
        self.assertEqual(list(stored_events), [])

        # Store pending events.
        event_store.put(pending)

        # Get domain events.
        domain_events = event_store.get(account.id)

        # Reconstruct the bank account.
        copy = None
        for domain_event in domain_events:
            assert isinstance(domain_event, CanMutateProtocol)
            copy = domain_event.mutate(copy)

        # Check copy has correct attribute values.
        assert copy is not None
        self.assertEqual(copy.id, account.id)
        self.assertEqual(copy.balance, Decimal("65.00"))

        # Get last event.
        events = tuple(event_store.get(account.id, desc=True, limit=1))
        self.assertEqual(len(events), 1)
        last_event = events[0]

        self.assertEqual(last_event.originator_id, account.id)
        assert type(last_event) is BankAccount.TransactionAppended
