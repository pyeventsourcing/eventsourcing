from __future__ import annotations

from datetime import datetime  # noqa: TC003
from typing import Any
from uuid import UUID, uuid4

import msgspec
from msgspec import field
from typing_extensions import TypeVar

from eventsourcing.domain import (
    BaseAggregate,
    CanInitAggregate,
    CanMutateAggregate,
    datetime_now_with_tzinfo,
    event,
    get_metadata_from_context,
)
from examples.dcb_enrolment.interface import (
    AlreadyJoinedError,
    CourseID,
    FullyBookedError,
    StudentID,
    TooManyCoursesError,
)


class DomainEvent(msgspec.Struct, frozen=True, kw_only=True):
    originator_id: str
    originator_version: int
    timestamp: datetime = field(default_factory=datetime_now_with_tzinfo)
    metadata: dict[str, str] = field(default_factory=get_metadata_from_context)
    event_id: UUID = field(default_factory=uuid4)
    # TODO: Maybe use the NIL_UUID and construct version 5
    #  UUID, like eventsourcing.domain.DomainEvent. At least
    #  align this with UmaDB event IDs.


class MsgspecStringIDEvent(DomainEvent, CanMutateAggregate[str], frozen=True):
    def _as_dict(self) -> dict[str, Any]:
        return {key: getattr(self, key) for key in self.__struct_fields__}


class MsgspecStringIDCreatedEvent(DomainEvent, CanInitAggregate[str], frozen=True):
    originator_topic: str


TID = TypeVar("TID", bound=str, default=str)


class MsgspecStringIDAggregate(BaseAggregate[TID]):
    class Event(MsgspecStringIDEvent, frozen=True):
        pass

    class Created(Event, MsgspecStringIDCreatedEvent, frozen=True):
        pass


class Aggregate(MsgspecStringIDAggregate[TID]):
    pass


class Student(Aggregate[StudentID]):
    @staticmethod
    def create_id() -> StudentID:
        return StudentID("student-" + str(uuid4()))

    def __init__(self, name: str, max_courses: int) -> None:
        self.name = name
        self.max_courses = max_courses
        self.course_ids: list[CourseID] = []

    @event("CourseJoined")
    def join_course(self, course_id: CourseID) -> None:
        if len(self.course_ids) >= self.max_courses:
            raise TooManyCoursesError
        self.course_ids.append(course_id)


class Course(Aggregate[CourseID]):
    @staticmethod
    def create_id() -> CourseID:
        return CourseID("course-" + str(uuid4()))

    def __init__(self, name: str, places: int) -> None:
        self.name = name
        self.places = places
        self.student_ids: list[StudentID] = []

    @event("StudentAccepted")
    def accept_student(self, student_id: StudentID) -> None:
        if len(self.student_ids) >= self.places:
            raise FullyBookedError
        if student_id in self.student_ids:
            raise AlreadyJoinedError
        self.student_ids.append(student_id)
