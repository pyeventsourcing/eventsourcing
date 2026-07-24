from __future__ import annotations

from eventsourcing.tests.postgres_utils import drop_tables
from examples.dcb_enrolment.test_enrolment import EnrolmentTestCase
from examples.dcb_enrolment_with_basic_objects.application import EnrolmentWithDCB


class TestEnrolmentWithDCB(EnrolmentTestCase):
    def test_enrolment_in_memory(self) -> None:
        self.assert_implementation(EnrolmentWithDCB())

    def test_enrolment_with_postgres(self) -> None:
        env = {
            "PERSISTENCE_MODULE": (
                "examples.dcb_enrolment_with_basic_objects.postgres_ts"
            ),
            "POSTGRES_DBNAME": "eventsourcing",
            "POSTGRES_HOST": "127.0.0.1",
            "POSTGRES_PORT": "5432",
            "POSTGRES_USER": "eventsourcing",
            "POSTGRES_PASSWORD": "eventsourcing",
        }
        try:
            self.assert_implementation(EnrolmentWithDCB(env=env))
        finally:
            drop_tables()

    def test_enrolment_with_umadb(self) -> None:
        env = {
            "PERSISTENCE_MODULE": "eventsourcing_umadb",
            "UMADB_URI": "http://127.0.0.1:50051",
        }
        self.assert_implementation(EnrolmentWithDCB(env=env))


del EnrolmentTestCase
