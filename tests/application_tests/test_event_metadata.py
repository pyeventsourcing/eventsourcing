import json
from unittest import TestCase
from uuid import uuid4

from eventsourcing.application import Application
from eventsourcing.domain import (
    Aggregate,
    DomainEvent,
    null_metadata_in_context,
    put_metadata_in_context,
)
from eventsourcing.persistence import StoredEvent


class TestEventMetadata(TestCase):
    def test_put_metadata_in_context(self) -> None:
        with (
            put_metadata_in_context({"user_id": "user-1"}),
            put_metadata_in_context({"correlation_id": "cor-1"}),
        ):
            event = DomainEvent(
                originator_id=uuid4(),
                originator_version=1,
            )
        self.assertEqual(event.metadata["user_id"], "user-1")
        self.assertEqual(event.metadata["correlation_id"], "cor-1")

    def test_set_metadata_in_context(self) -> None:
        # Use "recorded" metadata.
        with (
            put_metadata_in_context({"user_id": "user-1"}),
            null_metadata_in_context(),
        ):
            event = DomainEvent(
                originator_id=uuid4(),
                originator_version=1,
                metadata={"user_id": "user-2"},
            )
        self.assertEqual(event.metadata, {"user_id": "user-2"})

        # There is no "recorded" metadata.
        with (
            put_metadata_in_context({"user_id": "user-1"}),
            null_metadata_in_context(),
        ):
            event = DomainEvent(
                originator_id=uuid4(),
                originator_version=1,
            )
        self.assertEqual(event.metadata, {})

    def test_application_sets_metadata_when_getting_events(self) -> None:
        app = Application()
        # Metadata is set when events are triggered.
        with put_metadata_in_context({"user_id": "user-1"}):
            agg = Aggregate()

        # Event metadata is simply recorded.
        app.save(agg)

        # Recorded metadata is returned.
        with put_metadata_in_context({"user_id": "user-2"}):
            events = app.events.get(agg.id)
        for event in events:
            self.assertEqual(event.metadata, {"user_id": "user-1"})

        # Inject some legacy events recorded without metadata.
        stored_events = app.recorder.select_events(agg.id)
        legacy_stored_events = []
        new_id = uuid4()
        for stored_event in stored_events:
            state = json.loads(stored_event.state.decode())
            state.pop("metadata")
            legacy_stored_event = StoredEvent(
                originator_id=new_id,
                originator_version=stored_event.originator_version,
                topic=stored_event.topic,
                state=json.dumps(state).encode(),
            )
            legacy_stored_events.append(legacy_stored_event)
        app.recorder.insert_events(legacy_stored_events)

        with put_metadata_in_context({"user_id": "user-2"}):
            events = app.events.get(new_id)
        for event in events:
            self.assertEqual(event.metadata, {})
