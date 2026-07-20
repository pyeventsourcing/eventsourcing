from unittest import TestCase

from eventsourcing.dcb.application import DCBRepository
from eventsourcing.dcb.persistence import (
    DCBEventStore,
    NotFoundError,
)
from eventsourcing.dcb.popo import InMemoryDCBRecorder
from eventsourcing.domain import EnduringObject, TaggedEvent
from eventsourcing.errors import ProgrammingError
from eventsourcing.msgspec.immutable import MsgspecDecision
from eventsourcing.msgspec.transcoder import MsgspecTranscoder
from eventsourcing.persistence import TaggedEventMapper


class TestRepository(TestCase):
    def test_repository(self) -> None:
        repo = DCBRepository[MsgspecDecision](
            DCBEventStore(
                mapper=TaggedEventMapper(transcoder=MsgspecTranscoder()),
                recorder=InMemoryDCBRecorder(),
            )
        )
        with self.assertRaises(NotFoundError):
            repo.get("not-an-object", EnduringObject)


class TestEventStore(TestCase):
    def test_event_store(self) -> None:
        event_store = DCBEventStore[MsgspecDecision](
            mapper=TaggedEventMapper(MsgspecTranscoder()),
            recorder=InMemoryDCBRecorder(),
        )
        event_store.read()  # no args
        self.assertEqual(0, event_store.append([]))  # no events

        class MyMsgspecDecision(MsgspecDecision):
            a: int

        event: TaggedEvent[MsgspecDecision] = TaggedEvent(
            tags=["tag1", "tag2"],
            decision=MyMsgspecDecision(a=1),
        )
        position = event_store.append([event])
        self.assertEqual(position, 1)
        copies = list(event_store.read())
        self.assertEqual(len(copies), 1)
        copy = copies[0]

        self.assertEqual(type(copy), TaggedEvent)
        self.assertEqual(copy.tags, event.tags)
        self.assertEqual(copy.decision, event.decision)
        self.assertEqual(copy.uuid, event.uuid)


class TestInMemoryDCBRecorder(TestCase):
    def test_recorder(self) -> None:
        recorder = InMemoryDCBRecorder()
        with self.assertRaises(ProgrammingError):
            recorder.append([])  # no events
