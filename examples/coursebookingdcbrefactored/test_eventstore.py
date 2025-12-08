from unittest import TestCase

from eventsourcing.dcb.domain import Tagged
from eventsourcing.dcb.msgspecstruct import Decision, MsgspecStructMapper

# TODO: Actually test the event store independently of the example application.


class StudentRegistered(Decision):
    name: str
    max_courses: int


class TestMapper(TestCase):
    def test_mapper(self) -> None:
        mapper = MsgspecStructMapper()

        event = Tagged[StudentRegistered](
            tags=["student-1"],
            mutates=StudentRegistered(
                name="Sara",
                max_courses=2,
            ),
        )

        dcb_event = mapper.to_dcb_event(event)

        self.assertTrue(dcb_event.type.endswith("StudentRegistered"), dcb_event.type)
        self.assertTrue(dcb_event.tags, dcb_event.type)

        copy = mapper.to_domain_event(dcb_event)
        assert isinstance(copy, Tagged)  # for mypy
        assert isinstance(copy.mutates, StudentRegistered)  # for mypy

        self.assertEqual(copy.tags, event.tags)
        self.assertEqual(copy.mutates.name, event.mutates.name)
        self.assertEqual(copy.mutates.max_courses, event.mutates.max_courses)
