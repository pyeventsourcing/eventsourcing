from decimal import Decimal
from unittest.case import TestCase

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


class TestEventStore(TestCase):
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

        # Collect pending events.
        pending = account.collect_events()

        # Construct event store.
        transcoder = JSONTranscoder()
        transcoder.register(UUIDAsHex())
        transcoder.register(DecimalAsStr())
        transcoder.register(DatetimeAsISO())
        transcoder.register(EmailAddressAsStr())
        recorder = SQLiteAggregateRecorder(SQLiteDatastore(":memory:"))
        event_store = EventStore(
            mapper=Mapper(transcoder),
            recorder=recorder,
        )
        recorder.create_table()

        # Get last event.
        last_event = event_store.get(account.id, desc=True, limit=1)
        assert list(last_event) == []

        # Store pending events.
        event_store.put(pending)

        # Get domain events.
        domain_events = event_store.get(account.id)

        # Reconstruct the bank account.
        copy = None
        for domain_event in domain_events:
            copy = domain_event.mutate(copy)

        # Check copy has correct attribute values.
        assert copy.id == account.id
        assert copy.balance == Decimal("65.00")

        # Get last event.
        events = event_store.get(account.id, desc=True, limit=1)
        events = list(events)
        assert len(events) == 1
        last_event = events[0]

        assert last_event.originator_id == account.id
        assert type(last_event) == BankAccount.TransactionAppended
