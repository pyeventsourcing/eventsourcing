from __future__ import annotations

from unittest import TestCase

from eventsourcing.application import AggregatesApplication
from examples.dcb_enrolment.interface import (
    AlreadyJoinedError,
    CourseNotFoundError,
    EnrolmentInterface,
    FullyBookedError,
    StudentNotFoundError,
    TooManyCoursesError,
)


class EnrolmentTestCase(TestCase):
    def assert_implementation(self, app: EnrolmentInterface) -> None:
        # Register courses.
        position0, dcb = app.register_course("Dynamic Consistency Boundaries", places=5)
        is_aggregates = isinstance(app, AggregatesApplication)
        position, maths = app.register_course("Maths", places=5)
        self.assertEqual(position, position0 + 1)
        position, biology = app.register_course("Biology", places=5)
        self.assertEqual(position, position0 + 2)
        position, french = app.register_course("French", places=5)
        self.assertEqual(position, position0 + 3)
        position, spanish = app.register_course("Spanish", places=5)
        self.assertEqual(position, position0 + 4)

        # Register students.
        position, sara = app.register_student("Sara", max_courses=3)
        self.assertEqual(position, position0 + 5)
        position, mollie = app.register_student("Mollie", max_courses=3)
        self.assertEqual(position, position0 + 6)
        position, allard = app.register_student("Allard", max_courses=3)
        self.assertEqual(position, position0 + 7)
        position, grace = app.register_student("Grace", max_courses=3)
        self.assertEqual(position, position0 + 8)
        position, bastian = app.register_student("Bastian", max_courses=3)
        self.assertEqual(position, position0 + 9)
        position, greg = app.register_student("Greg", max_courses=3)
        self.assertEqual(position, position0 + 10)
        position, katherine = app.register_student("Katherine", max_courses=3)
        self.assertEqual(position, position0 + 11)

        # Enrol students for "Dynamic Consistency Boundaries" course.
        position = app.join_course(sara, dcb)

        if is_aggregates:
            position0 += 1

        self.assertEqual(position, position0 + 12)

        position = app.join_course(mollie, dcb)

        if is_aggregates:
            position0 += 1

        self.assertEqual(position, position0 + 13)

        position = app.join_course(allard, dcb)

        if is_aggregates:
            position0 += 1

        self.assertEqual(position, position0 + 14)

        position = app.join_course(grace, dcb)

        if is_aggregates:
            position0 += 1

        self.assertEqual(position, position0 + 15)

        position = app.join_course(bastian, dcb)

        if is_aggregates:
            position0 += 1

        self.assertEqual(position, position0 + 16)

        # Greg can't join because the course is full.
        with self.assertRaises(FullyBookedError):
            app.join_course(greg, dcb)

        # Greg joins other courses instead.
        position = app.join_course(greg, french)

        if is_aggregates:
            position0 += 1

        self.assertEqual(position, position0 + 17)

        position = app.join_course(greg, spanish)

        if is_aggregates:
            position0 += 1

        self.assertEqual(position, position0 + 18)

        position = app.join_course(greg, maths)

        if is_aggregates:
            position0 += 1

        self.assertEqual(position, position0 + 19)

        # Greg has enough to do already.
        with self.assertRaises(TooManyCoursesError):
            app.join_course(greg, biology)

        # Katherine also does "French".
        position = app.join_course(katherine, french)

        if is_aggregates:
            position0 += 1

        self.assertEqual(position, position0 + 20)

        # Katherine already does "French".
        with self.assertRaises(AlreadyJoinedError):
            app.join_course(katherine, french)

        # Course not found.
        with self.assertRaises(CourseNotFoundError):
            course_id = "not-a-course"
            app.join_course(grace, course_id)

        # Student not found.
        with self.assertRaises(StudentNotFoundError):
            app.join_course("not-a-student", dcb)

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
