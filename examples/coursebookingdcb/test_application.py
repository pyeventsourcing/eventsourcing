from __future__ import annotations

from eventsourcing.tests.postgres_utils import drop_tables
from examples.coursebooking.test_enrolment import EnrolmentTestCase
from examples.coursebookingdcb.application import EnrolmentWithDCB


class TestEnrolmentWithDCB(EnrolmentTestCase):
    def test_enrolment_in_memory(self):
        env = {"PERSISTENCE_MODULE": "eventsourcing.dcb.popo"}
        self.assert_implementation(EnrolmentWithDCB(env))

    def test_enrolment_with_postgres(self) -> None:
        env = {
            "PERSISTENCE_MODULE": "examples.coursebookingdcb.postgres_ts",
            "POSTGRES_DBNAME": "eventsourcing",
            "POSTGRES_HOST": "127.0.0.1",
            "POSTGRES_PORT": "5432",
            "POSTGRES_USER": "eventsourcing",
            "POSTGRES_PASSWORD": "eventsourcing",  # noqa: S105
        }
        try:
            self.assert_implementation(EnrolmentWithDCB(env))
        finally:
            drop_tables()

del EnrolmentTestCase
