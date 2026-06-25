from __future__ import annotations

from typing import ClassVar

from eventsourcing.application import AggregateNotFoundError, Application
from eventsourcing.msgspec.mapper import MsgspecMapper
from eventsourcing.utils import get_topic
from examples.dcb_enrolment.domainmodel import Course, Student
from examples.dcb_enrolment.interface import (
    CourseID,
    CourseNotFoundError,
    EnrolmentInterface,
    StudentID,
    StudentNotFoundError,
)


class EnrolmentWithAggregates(Application[str], EnrolmentInterface):
    env: ClassVar[dict[str, str]] = {
        "MAPPER_TOPIC": get_topic(MsgspecMapper),
        "ORIGINATOR_ID_TYPE": "text",
    }

    def register_student(self, name: str, max_courses: int) -> StudentID:
        student = Student(name, max_courses=max_courses)
        self.save(student)
        return student.id

    def register_course(self, name: str, places: int) -> CourseID:
        course = Course(name, places=places)
        self.save(course)
        return course.id

    def join_course(self, student_id: StudentID, course_id: CourseID) -> None:
        course = self.get_course(course_id)
        student = self.get_student(student_id)
        course.accept_student(student_id)
        student.join_course(course_id)
        self.save(course, student)

    def list_students_for_course(self, course_id: CourseID) -> list[str]:
        course = self.get_course(course_id)
        return [self.get_student(s).name for s in course.student_ids]

    def list_courses_for_student(self, student_id: StudentID) -> list[str]:
        student = self.get_student(student_id)
        return [self.get_course(s).name for s in student.course_ids]

    def get_student(self, student_id: StudentID) -> Student:
        try:
            return self.repository.get(student_id)
        except AggregateNotFoundError:
            raise StudentNotFoundError from None

    def get_course(self, course_id: CourseID) -> Course:
        try:
            return self.repository.get(course_id)
        except AggregateNotFoundError:
            raise CourseNotFoundError from None
