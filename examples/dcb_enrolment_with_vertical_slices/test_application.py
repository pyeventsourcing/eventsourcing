from __future__ import annotations

from eventsourcing.domain import ProgrammingError
from eventsourcing.persistence import IntegrityError
from eventsourcing.tests.postgres_utils import drop_tables
from examples.dcb_enrolment.interface import (
    EnrolmentInterface,
    FullyBookedError,
    TooManyCoursesError,
)
from examples.dcb_enrolment.test_enrolment import EnrolmentTestCase
from examples.dcb_enrolment_with_vertical_slices.application import (
    EnrolmentWithVerticalSlices,
    StudentJoinsCourse,
    StudentLeavesCourse,
    UpdateMaxCourses,
    UpdateStudentName,
)


class TestEnrolmentWithVerticalSlices(EnrolmentTestCase):
    def test_enrolment_in_memory(self) -> None:
        self.assert_implementation(EnrolmentWithVerticalSlices())

    def test_enrolment_with_postgres(self) -> None:
        env = {
            "PERSISTENCE_MODULE": "eventsourcing.dcb.postgres_tt",
            "POSTGRES_DBNAME": "eventsourcing",
            "POSTGRES_HOST": "127.0.0.1",
            "POSTGRES_PORT": "5432",
            "POSTGRES_USER": "eventsourcing",
            "POSTGRES_PASSWORD": "eventsourcing",
        }
        try:
            self.assert_implementation(EnrolmentWithVerticalSlices(env))
        finally:
            drop_tables()

    def test_enrolment_with_umadb(self) -> None:
        env = {
            "PERSISTENCE_MODULE": "eventsourcing_umadb",
            "UMADB_URI": "http://127.0.0.1:50051",
        }
        self.assert_implementation(EnrolmentWithVerticalSlices(env))

    def assert_implementation(self, app: EnrolmentInterface) -> None:
        super().assert_implementation(app)

        assert isinstance(app, EnrolmentWithVerticalSlices)
        # Register student.
        student_id = app.register_student(name="Max", max_courses=4)

        # Update name.
        app.update_student_name(student_id, "Maxine")
        student = app.get_student(student_id)
        self.assertEqual("Maxine", student.name)

        # Register course.
        course_id = app.register_course(name="Bio", places=3)

        # Update name.
        app.update_course_name(course_id, "Biology")
        course = app.get_course(course_id)
        self.assertEqual("Biology", course.name)

        # Join course.
        app.join_course(student_id=student_id, course_id=course_id)
        student = app.get_student(student_id)
        course = app.get_course(course_id)
        self.assertEqual([course_id], student.course_ids)
        self.assertEqual([student_id], course.student_ids)

        # List students for course.
        names = app.list_students_for_course(course_id)
        self.assertEqual(["Maxine"], names)

        # List courses for student.
        names = app.list_courses_for_student(student_id)
        self.assertEqual(["Biology"], names)

        # Leave course.
        app.leave_course(student_id=student_id, course_id=course_id)
        student = app.get_student(student_id)
        course = app.get_course(course_id)
        self.assertEqual([], student.course_ids)
        self.assertEqual([], course.student_ids)

        # Update max_courses for student.
        app.update_max_courses(student_id, 0)
        student = app.get_student(student_id)
        self.assertEqual(0, student.max_courses)

        # Update places for course.
        app.update_places(course_id, 0)
        course = app.get_course(course_id)
        self.assertEqual(0, course.places)

        # Check leaves course, updated max_courses, and places
        # events are effective when joining course.
        with self.assertRaises(FullyBookedError):
            app.join_course(student_id=student_id, course_id=course_id)

        # Increase places.
        app.update_places(course_id, 1)

        with self.assertRaises(TooManyCoursesError):
            app.join_course(student_id=student_id, course_id=course_id)

        # Increase max_courses.
        app.update_max_courses(student_id, 1)

        # Student can now rejoin course.
        app.join_course(student_id=student_id, course_id=course_id)

        # Check leaving a course doesn't conflict with concurrent name changes.
        leave = StudentLeavesCourse(student_id, course_id)
        app.repository.project_perspective(leave)
        leave.execute()
        app.update_student_name(student_id, "Mollie")
        app.update_course_name(course_id, "Bio-science")
        app.repository.save(leave)

        # Check leaving a course doesn't conflict with concurrent name changes.
        join = StudentJoinsCourse(student_id, course_id)
        app.repository.project_perspective(join)
        join.execute()
        app.update_student_name(student_id, "Millie")
        app.update_course_name(course_id, "Biological-science")
        app.repository.save(join)

        # Check leaving doesn't conflict with updating max_courses and places.
        leave = StudentLeavesCourse(student_id, course_id)
        app.repository.project_perspective(leave)
        leave.execute()
        app.update_max_courses(student_id, 31)
        app.update_places(course_id, 28)
        app.repository.save(leave)

        # Check joining does conflict with updating max_courses and places.
        join = StudentJoinsCourse(student_id, course_id)
        app.repository.project_perspective(join)
        join.execute()
        app.update_max_courses(student_id, 39)
        app.update_places(course_id, 43)
        with self.assertRaises(IntegrityError):
            app.repository.save(join)

        # Check updating max_courses doesn't conflict with updating name.
        rename = UpdateStudentName(student_id, "Maddy")
        app.repository.project_perspective(rename)
        rename.execute()
        app.update_max_courses(student_id, 101)
        app.repository.save(rename)

        max_courses = UpdateMaxCourses(student_id, 50)
        app.repository.project_perspective(max_courses)
        max_courses.execute()
        app.update_student_name(student_id, "Mandy")
        app.repository.save(max_courses)

        student = app.get_student(student_id)
        self.assertEqual("Mandy", student.name)
        self.assertEqual(50, student.max_courses)
        self.assertEqual([], student.course_ids)

        # Can't call non-command underscore methods.
        with self.assertRaisesRegex(ProgrammingError, "cannot be used"):
            student._()  # type: ignore[call-arg]


del EnrolmentTestCase
