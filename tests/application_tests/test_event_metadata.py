from unittest import TestCase
from uuid import uuid4

from eventsourcing.dataclasses import Decision
from eventsourcing.domain import (
    AggregateEvent,
)
from eventsourcing.metadata import (
    null_metadata_in_context,
    put_metadata_in_context,
)
from eventsourcing.persistence import StoredEvent
from eventsourcing.tests.application import BankAccountsWithPydantic


class TestEventMetadata(TestCase):
    def test_put_metadata_in_context(self) -> None:
        with (
            put_metadata_in_context({"user_id": "user-1"}),
            put_metadata_in_context({"correlation_id": "cor-1"}),
        ):
            event = AggregateEvent(
                originator_id=str(uuid4()),
                originator_version=1,
                decision=Decision(),
            )
        self.assertEqual(event.metadata["user_id"], "user-1")
        self.assertEqual(event.metadata["correlation_id"], "cor-1")

    def test_set_metadata_in_context(self) -> None:
        # Use "recorded" metadata.
        with (
            put_metadata_in_context({"user_id": "user-1"}),
            null_metadata_in_context(),
        ):
            event = AggregateEvent(
                originator_id=str(uuid4()),
                originator_version=1,
                metadata={"user_id": "user-2"},
                decision=Decision(),
            )
        self.assertEqual(event.metadata, {"user_id": "user-2"})

        # There is no "recorded" metadata.
        with (
            put_metadata_in_context({"user_id": "user-1"}),
            null_metadata_in_context(),
        ):
            event = AggregateEvent(
                originator_id=str(uuid4()),
                originator_version=1,
                decision=Decision(),
            )
        self.assertEqual(event.metadata, {})

    def test_application_sets_metadata_when_getting_events(self) -> None:
        app = BankAccountsWithPydantic()
        # Metadata is set when events are triggered.
        with put_metadata_in_context({"user_id": "user-1"}):
            account_id = app.open_account("Phil", "phil@example.com")

        # Recorded metadata is returned.
        with put_metadata_in_context({"user_id": "user-2"}):
            events = app.events.get(account_id)
        for event in events:
            self.assertEqual(event.metadata, {"user_id": "user-1"})

        # Inject some legacy events recorded without metadata.
        stored_events = app.recorder.select_events(account_id)
        legacy_stored_events = []
        new_id = str(uuid4())
        for stored_event in stored_events:
            legacy_stored_event = StoredEvent(
                originator_id=new_id,
                originator_version=stored_event.originator_version,
                topic=stored_event.topic,
                state=stored_event.state,
            )
            legacy_stored_events.append(legacy_stored_event)
        app.recorder.insert_events(legacy_stored_events)

        with put_metadata_in_context({"user_id": "user-2"}):
            events = app.events.get(new_id)
        for event in events:
            self.assertEqual(event.metadata, {})
