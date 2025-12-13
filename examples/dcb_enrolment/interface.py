from __future__ import annotations

from abc import ABC, abstractmethod
from typing import NewType

StudentID = NewType("StudentID", str)

CourseID = NewType("CourseID", str)


class EnrolmentInterface(ABC):
    @abstractmethod
    def register_student(self, name: str, max_courses: int) -> StudentID:
        """
        Register a new student.
        """

    @abstractmethod
    def register_course(self, name: str, places: int) -> CourseID:
        """
        Register a new course.
        """

    @abstractmethod
    def join_course(self, student_id: StudentID, course_id: CourseID) -> None:
        """
        Enrol a student on a course.
        """

    @abstractmethod
    def list_students_for_course(self, course_id: CourseID) -> list[str]:
        """
        List students enrolled on a course.
        """

    @abstractmethod
    def list_courses_for_student(self, student_id: StudentID) -> list[str]:
        """
        List courses enrolled by a student.
        """


class StudentNotFoundError(Exception):
    """
    Raised when a student is not registered.
    """


class CourseNotFoundError(Exception):
    """
    Raised when a course is not registered.
    """


class TooManyCoursesError(Exception):
    """
    Raised when a student is already enrolled to a maximum number of courses.
    """


class FullyBookedError(Exception):
    """
    Raised when a course already has a maximum number of enrolled students.
    """


class NotAlreadyJoinedError(Exception):
    """
    Raised when a student is not already enrolled on a course.
    """


class AlreadyJoinedError(Exception):
    """
    Raised when a student is already enrolled on a course.
    """
