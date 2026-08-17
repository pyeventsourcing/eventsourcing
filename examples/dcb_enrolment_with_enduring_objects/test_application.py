from __future__ import annotations

from typing import TYPE_CHECKING, override

from eventsourcing_umadb.server_fixture import temp_umadb_server

from eventsourcing.errors import ProgrammingError
from eventsourcing.persistence import IntegrityError
from eventsourcing.tests.postgres_utils import drop_tables
from examples.dcb_enrolment.test_enrolment import EnrolmentTestCase
from examples.dcb_enrolment_with_enduring_objects.application import (
    Course,
    EnrolmentWithEnduringObjects,
    Student,
    StudentAndCourse,
)

if TYPE_CHECKING:
    from examples.dcb_enrolment.interface import EnrolmentInterface


class TestEnrolmentWithEnduringObjects(EnrolmentTestCase):
    def test_enrolment_in_memory(self) -> None:
        self.assert_implementation(EnrolmentWithEnduringObjects())

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
            self.assert_implementation(EnrolmentWithEnduringObjects(env=env))
        finally:
            drop_tables()

    def test_enrolment_with_umadb(self) -> None:
        with temp_umadb_server() as url:
            env = {
                "PERSISTENCE_MODULE": "eventsourcing_umadb",
                "UMADB_URI": url,
            }
            self.assert_implementation(EnrolmentWithEnduringObjects(env=env))

    @override
    def assert_implementation(self, app: EnrolmentInterface) -> None:
        super().assert_implementation(app)

        assert isinstance(app, EnrolmentWithEnduringObjects)
        # Register student.
        student_id = app.register_student(name="Max", max_courses=4)

        # Update name.
        app.update_student_name(student_id, "Maxine")
        student = app.get_student(student_id)
        self.assertEqual("Maxine", student.name)

        # Update max_courses.
        app.update_max_courses(student_id, 10)
        student = app.get_student(student_id)
        self.assertEqual(10, student.max_courses)

        # Register course.
        course_id = app.register_course(name="Bio", places=3)

        # Update name.
        app.update_course_name(course_id, "Biology")
        course = app.get_course(course_id)
        self.assertEqual("Biology", course.name)

        # Update places.
        app.update_places(course_id, 10)
        course = app.get_course(course_id)
        self.assertEqual(10, course.places)

        # Join course.
        app.join_course(student_id=student_id, course_id=course_id)
        student = app.get_student(student_id)
        course = app.get_course(course_id)
        self.assertEqual(student.course_ids, [course_id])
        self.assertEqual(course.student_ids, [student_id])

        # Leave course.
        app.leave_course(student_id=student_id, course_id=course_id)
        student = app.get_student(student_id)
        course = app.get_course(course_id)
        self.assertEqual(student.course_ids, [])
        self.assertEqual(course.student_ids, [])

        # Can operate on enduring objects in group.
        group = app.repository.get_group(StudentAndCourse, student_id, course_id)
        group.student.update_max_courses(100)
        app.repository.save(group.student)
        student = app.get_student(student_id)
        self.assertEqual(100, student.max_courses)

        # Check concurrent change raises IntegrityError.
        group = app.repository.get_group(StudentAndCourse, student_id, course_id)
        group.student_joins_course()
        app.update_max_courses(student_id, 1)
        with self.assertRaises(IntegrityError):
            app.repository.save(group)

        # Check concurrent change raises IntegrityError.
        group = app.repository.get_group(StudentAndCourse, student_id, course_id)
        group.student_joins_course()
        app.update_student_name(student_id, "Maxy")
        with self.assertRaises(IntegrityError):
            app.repository.save(group)

        # Check get_many() preserves order.
        objs = app.repository.get_many(
            (course_id, student_id), classes=(Course, Student)
        )
        self.assertEqual([course_id, student_id], [o.id for o in objs if o])
        objs = app.repository.get_many(
            (student_id, course_id), classes=(Student, Course)
        )
        self.assertEqual([student_id, course_id], [o.id for o in objs if o])

        # Can't call non-command underscore methods.
        with self.assertRaisesRegex(ProgrammingError, "cannot be used"):
            student._(course_id=course_id)


del EnrolmentTestCase
