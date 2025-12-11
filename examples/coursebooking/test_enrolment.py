from __future__ import annotations

from typing import Any
from unittest import TestCase, TestSuite

from eventsourcing.tests.postgres_utils import drop_tables
from examples.coursebooking.interface import (
    AlreadyJoinedError,
    CourseID,
    CourseNotFoundError,
    EnrolmentInterface,
    FullyBookedError,
    StudentID,
    StudentNotFoundError,
    TooManyCoursesError,
)


class EnrolmentTestCase(TestCase):
    def assert_implementation(self, app: EnrolmentInterface) -> None:
        # Register courses.
        dcb = app.register_course("Dynamic Consistency Boundaries", places=5)
        maths = app.register_course("Maths", places=5)
        biology = app.register_course("Biology", places=5)
        french = app.register_course("French", places=5)
        spanish = app.register_course("Spanish", places=5)

        # Register students.
        sara = app.register_student("Sara", max_courses=3)
        mollie = app.register_student("Mollie", max_courses=3)
        allard = app.register_student("Allard", max_courses=3)
        grace = app.register_student("Grace", max_courses=3)
        bastian = app.register_student("Bastian", max_courses=3)
        greg = app.register_student("Greg", max_courses=3)
        katherine = app.register_student("Katherine", max_courses=3)

        # Enrol students for "Dynamic Consistency Boundaries" course.
        app.join_course(sara, dcb)
        app.join_course(mollie, dcb)
        app.join_course(allard, dcb)
        app.join_course(grace, dcb)
        app.join_course(bastian, dcb)

        # Greg can't join because the course is full.
        with self.assertRaises(FullyBookedError):
            app.join_course(greg, dcb)

        # Greg joins other courses instead.
        app.join_course(greg, french)
        app.join_course(greg, spanish)
        app.join_course(greg, maths)

        # Greg has enough to do already.
        with self.assertRaises(TooManyCoursesError):
            app.join_course(greg, biology)

        # Katherine also does "French".
        app.join_course(katherine, french)

        # Katherine already does "French".
        with self.assertRaises(AlreadyJoinedError):
            app.join_course(katherine, french)

        # Course not found.
        with self.assertRaises(CourseNotFoundError):
            app.join_course(grace, CourseID("not-a-course"))

        # Student not found.
        with self.assertRaises(StudentNotFoundError):
            app.join_course(StudentID("not-a-student"), dcb)

        # List students for "Dynamic Consistency Boundaries" course.
        students = app.list_students_for_course(dcb)
        self.assertEqual(students, ["Sara", "Mollie", "Allard", "Grace", "Bastian"])

        # List students for "French" course.
        students = app.list_students_for_course(french)
        self.assertEqual(students, ["Greg", "Katherine"])

        # List Sara's courses.
        courses = app.list_courses_for_student(sara)
        self.assertEqual(courses, ["Dynamic Consistency Boundaries"])

        # List Greg's courses.
        courses = app.list_courses_for_student(greg)
        self.assertEqual(courses, ["French", "Spanish", "Maths"])
