from __future__ import annotations

from eventsourcing.domain import event
from eventsourcing.msgspec.mutablemodel import Aggregate
from examples.dcb_enrolment.interface import (
    AlreadyJoinedError,
    CourseID,
    FullyBookedError,
    StudentID,
    TooManyCoursesError,
)


class Student(Aggregate[StudentID]):
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
