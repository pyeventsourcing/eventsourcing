from __future__ import annotations

from eventsourcing.application import AggregateNotFoundError
from eventsourcing.msgspec import AggregatesApplication
from examples.dcb_enrolment.domainmodel import Course, Student
from examples.dcb_enrolment.interface import (
    CourseNotFoundError,
    EnrolmentInterface,
    StudentNotFoundError,
)


class EnrolmentWithAggregates(AggregatesApplication, EnrolmentInterface):

    def register_student(self, name: str, max_courses: int) -> str:
        student = Student(name, max_courses=max_courses)
        self.save(student)
        return student.id

    def register_course(self, name: str, places: int) -> str:
        course = Course(name, places=places)
        self.save(course)
        return course.id

    def join_course(self, student_id: str, course_id: str) -> None:
        course = self.get_course(course_id)
        student = self.get_student(student_id)
        course.accept_student(student_id)
        student.join_course(course_id)
        self.save(course, student)

    def list_students_for_course(self, course_id: str) -> list[str]:
        course = self.get_course(course_id)
        return [self.get_student(s).name for s in course.student_ids]

    def list_courses_for_student(self, student_id: str) -> list[str]:
        student = self.get_student(student_id)
        return [self.get_course(s).name for s in student.course_ids]

    def get_student(self, student_id: str) -> Student:
        try:
            return self.repository.get(student_id, Student)
        except AggregateNotFoundError:
            raise StudentNotFoundError from None

    def get_course(self, course_id: str) -> Course:
        try:
            return self.repository.get(course_id, Course)
        except AggregateNotFoundError:
            raise CourseNotFoundError from None
