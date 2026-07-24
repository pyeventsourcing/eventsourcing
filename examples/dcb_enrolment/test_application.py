from __future__ import annotations

from eventsourcing.persistence import IntegrityError
from eventsourcing.tests.postgres_utils import drop_tables
from examples.dcb_enrolment.application import EnrolmentWithAggregates
from examples.dcb_enrolment.test_enrolment import EnrolmentTestCase


class TestEnrolmentWithAggregates(EnrolmentTestCase):
    def test_enrolment_in_memory(self) -> None:
        self.assert_implementation(EnrolmentWithAggregates())

    def test_enrolment_with_postgres(self) -> None:
        env = {
            "PERSISTENCE_MODULE": "eventsourcing.postgres",
            "POSTGRES_DBNAME": "eventsourcing",
            "POSTGRES_HOST": "127.0.0.1",
            "POSTGRES_PORT": "5432",
            "POSTGRES_USER": "eventsourcing",
            "POSTGRES_PASSWORD": "eventsourcing",
        }
        try:
            app = EnrolmentWithAggregates(env=env)
            self.assert_implementation(app)
        finally:
            drop_tables()

    def test_consistency_boundary(self) -> None:
        app = EnrolmentWithAggregates()

        # Register courses.
        french = app.register_course("French", places=5)

        # Register students.
        sara = app.register_student("Sara", max_courses=3)
        bastian = app.register_student("Bastian", max_courses=3)

        # Try to break recorded consistency with concurrent operation.
        assert isinstance(app, EnrolmentWithAggregates)
        student = app.get_student(sara)
        course = app.get_course(french)
        student.join_course(course.id)
        course.accept_student(student.id)

        # During this operation, Bastian joins French.
        app.join_course(bastian, french)

        # Can't proceed with concurrent operation because course changed.
        with self.assertRaises(IntegrityError):
            app.save(student, course)

        # Check Sara doesn't have French, and French doesn't have Sara.
        self.assertNotIn("Sara", app.list_students_for_course(french))
        self.assertNotIn("French", app.list_courses_for_student(sara))


# test_cases = (TestEnrolmentWithAggregates, TestEnrolmentConsistency)
#
#
# def load_tests(loader: TestLoader, _: TestSuite, __: str | None) -> TestSuite:
#     suite = TestSuite()
#     for test_class in test_cases:
#         tests = loader.loadTestsFromTestCase(test_class)
#         suite.addTests(tests)
#     return suite
