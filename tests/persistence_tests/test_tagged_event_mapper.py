from unittest import TestCase

from eventsourcing.domain import TaggedEvent
from eventsourcing.msgspec import Decision, Transcoder
from eventsourcing.persistence import TaggedEventMapper


class StudentRegistered(Decision):
    name: str
    max_courses: int


class TestTaggedEventMapper(TestCase):
    def test_mapper(self) -> None:
        mapper = TaggedEventMapper[Decision](Transcoder())

        event = TaggedEvent[StudentRegistered](
            tags=["student-1"],
            decision=StudentRegistered(
                name="Sara",
                max_courses=2,
            ),
        )

        dcb_event = mapper.to_dcb_event(event)

        self.assertTrue(dcb_event.type.endswith("StudentRegistered"), dcb_event.type)
        self.assertTrue(dcb_event.tags, dcb_event.type)

        copy = mapper.to_tagged_event(dcb_event)
        assert isinstance(copy, TaggedEvent)  # for mypy
        assert isinstance(copy.decision, StudentRegistered)  # for mypy

        self.assertEqual(copy.tags, event.tags)
        self.assertEqual(copy.decision.name, event.decision.name)
        self.assertEqual(copy.decision.max_courses, event.decision.max_courses)
