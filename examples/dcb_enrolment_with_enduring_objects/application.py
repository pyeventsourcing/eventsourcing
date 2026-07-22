from __future__ import annotations

from typing import cast

from eventsourcing.domain import (
    event,
)
from eventsourcing.pydantic import (
    DCBApplication,
    Decision,
    EnduringObject,
    Group,
)
from examples.dcb_enrolment.interface import (
    AlreadyJoinedError,
    CourseNotFoundError,
    EnrolmentInterface,
    FullyBookedError,
    NotAlreadyJoinedError,
    StudentNotFoundError,
    TooManyCoursesError,
)


class StudentDecision(Decision):
    student_id: str


class CourseDecision(Decision):
    course_id: str


class StudentRegistered(StudentDecision):
    name: str
    max_courses: int


class StudentNameUpdated(StudentDecision):
    name: str


class StudentMaxCoursesUpdated(StudentDecision):
    max_courses: int


class CourseRegistered(CourseDecision):
    course_id: str
    name: str
    places: int


class CourseNameUpdated(CourseDecision):
    course_id: str
    name: str


class CoursePlacesUpdated(CourseDecision):
    course_id: str
    places: int


class StudentJoinedCourse(StudentDecision, CourseDecision):
    pass


class StudentLeftCourse(StudentDecision, CourseDecision):
    pass


class Student(EnduringObject):
    @event(StudentRegistered)
    def __init__(self, name: str, max_courses: int) -> None:
        self.name = name
        self.max_courses = max_courses
        self.course_ids: list[str] = []

    @event(StudentNameUpdated)
    def update_name(self, name: str) -> None:
        self.name = name

    @event(StudentMaxCoursesUpdated)
    def update_max_courses(self, max_courses: int) -> None:
        self.max_courses = max_courses

    @event(StudentJoinedCourse)
    def _(self, course_id: str) -> None:
        if len(self.course_ids) >= self.max_courses:
            raise TooManyCoursesError
        self.course_ids.append(course_id)

    @event(StudentLeftCourse)
    def _(self, course_id: str) -> None:
        self.course_ids.remove(course_id)


class Course(EnduringObject):
    @event(CourseRegistered)
    def __init__(self, name: str, places: int) -> None:
        self.name = name
        self.places = places
        self.student_ids: list[str] = []

    @event(CourseNameUpdated)
    def update_name(self, name: str) -> None:
        self.name = name

    @event(CoursePlacesUpdated)
    def update_places(self, places: int) -> None:
        self.places = places

    @event(StudentJoinedCourse)
    def _(self, student_id: str) -> None:
        if student_id in self.student_ids:
            raise AlreadyJoinedError
        if len(self.student_ids) >= self.places:
            raise FullyBookedError
        self.student_ids.append(student_id)

    @event(StudentLeftCourse)
    def _(self, student_id: str) -> None:
        if student_id not in self.student_ids:
            raise NotAlreadyJoinedError
        self.student_ids.remove(student_id)


class StudentAndCourse(Group):
    def __init__(
        self,
        student: Student | None,
        course: Course | None,
    ) -> None:
        if course is None:
            raise CourseNotFoundError
        if student is None:
            raise StudentNotFoundError
        self.student = student
        self.course = course

    def student_joins_course(self) -> None:
        # The DCB magic: one event for "one fact".
        self.trigger_event(
            StudentJoinedCourse,
            student_id=self.student.id,
            course_id=self.course.id,
        )

    def student_leaves_course(self) -> None:
        # The DCB magic: one event for "one fact".
        self.trigger_event(
            StudentLeftCourse,
            student_id=self.student.id,
            course_id=self.course.id,
        )


class EnrolmentWithEnduringObjects(DCBApplication, EnrolmentInterface):
    def register_student(self, name: str, max_courses: int) -> str:
        student = Student(name=name, max_courses=max_courses)
        self.repository.save(student)
        return student.id

    def register_course(self, name: str, places: int) -> str:
        course = Course(name=name, places=places)
        self.repository.save(course)
        return course.id

    def join_course(self, student_id: str, course_id: str) -> None:
        group = self.repository.get_group(StudentAndCourse, student_id, course_id)
        group.student_joins_course()
        self.repository.save(group)

    def leave_course(self, student_id: str, course_id: str) -> None:
        group = self.repository.get_group(StudentAndCourse, student_id, course_id)
        group.student_leaves_course()
        self.repository.save(group)

    def list_students_for_course(self, course_id: str) -> list[str]:
        course = self.get_course(course_id)
        students = self.repository.get_many(course.student_ids, cls=Student)
        return [cast(Student, c).name for c in students if c is not None]

    def list_courses_for_student(self, student_id: str) -> list[str]:
        student = self.get_student(student_id)
        courses = self.repository.get_many(student.course_ids, cls=Course)
        return [cast(Course, c).name for c in courses if c is not None]

    def update_student_name(self, student_id: str, name: str) -> None:
        student = self.get_student(student_id)
        student.update_name(name)
        self.repository.save(student)

    def update_max_courses(self, student_id: str, max_courses: int) -> None:
        student = self.get_student(student_id)
        student.update_max_courses(max_courses)
        self.repository.save(student)

    def update_course_name(self, course_id: str, name: str) -> None:
        course = self.get_course(course_id)
        course.update_name(name)
        self.repository.save(course)

    def update_places(self, course_id: str, max_courses: int) -> None:
        course = self.get_course(course_id)
        course.update_places(max_courses)
        self.repository.save(course)

    def get_student(self, student_id: str) -> Student:
        return self.repository.get(student_id, Student)

    def get_course(self, course_id: str) -> Course:
        return self.repository.get(course_id, Course)
