from unittest import TestCase

from eventsourcing.dcb.application import DcbRepository
from eventsourcing.dcb.persistence import (
    DcbEventStore,
    NotFoundError,
)
from eventsourcing.dcb.popo import InMemoryDcbRecorder
from eventsourcing.domain import EnduringObject, TaggedEvent
from eventsourcing.errors import ProgrammingError
from eventsourcing.msgspec.immutable import Decision
from eventsourcing.msgspec.transcoder import Transcoder
from eventsourcing.persistence import TaggedEventMapper


class TestRepository(TestCase):
    def test_repository(self) -> None:
        repo = DcbRepository[Decision](
            DcbEventStore(
                mapper=TaggedEventMapper(transcoder=Transcoder()),
                recorder=InMemoryDcbRecorder(),
            )
        )
        with self.assertRaises(NotFoundError):
            repo.get("not-an-object", EnduringObject)


class TestEventStore(TestCase):
    def test_event_store(self) -> None:
        event_store = DcbEventStore[Decision](
            mapper=TaggedEventMapper(Transcoder()),
            recorder=InMemoryDcbRecorder(),
        )
        event_store.read()  # no args
        self.assertEqual(0, event_store.append([]))  # no events

        class MyMsgspecDecision(Decision):
            a: int

        event: TaggedEvent[Decision] = TaggedEvent(
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


class TestInMemoryDcbRecorder(TestCase):
    def test_recorder(self) -> None:
        recorder = InMemoryDcbRecorder()
        with self.assertRaises(ProgrammingError):
            recorder.append([])  # no events
