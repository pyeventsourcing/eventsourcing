from __future__ import annotations

from eventsourcing.domain import ProgrammingError
from eventsourcing.persistence import IntegrityError
from examples.coursebooking.test_enrolment import EnrolmentTestCase
from examples.coursebookingdcbrefactored.application import (
    EnrolmentWithDCBRefactored,
    StudentAndCourse,
)
from examples.coursebookingdcbrefactored.test_application import \
    TestEnrolmentWithDCBRefactored


class TestEnrolmentWithUmaDB(TestEnrolmentWithDCBRefactored):
    def setUp(self) -> None:
        super().setUp()
        self.env["PERSISTENCE_MODULE"] = "eventsourcing_umadb"
        self.env["UMADB_URL"] = "https://127.0.0.1:50051"

    def construct_app(self) -> EnrolmentWithDCBRefactored:
        return EnrolmentWithDCBRefactored(self.env)

    def test_enrolment(self) -> None:
        super().test_enrolment()

        with self.construct_app() as app:

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
            app.repository.save(group)
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
            objs = app.repository.get_many(course_id, student_id)
            self.assertEqual([course_id, student_id], [o.id for o in objs if o])
            objs = app.repository.get_many(student_id, course_id)
            self.assertEqual([student_id, course_id], [o.id for o in objs if o])

            # Can't call non-command underscore methods.
            with self.assertRaisesRegex(ProgrammingError, "cannot be used"):
                student._(course_id=course_id)


del EnrolmentTestCase
