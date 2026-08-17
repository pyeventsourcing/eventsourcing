from __future__ import annotations

from eventsourcing_umadb.server_fixture import temp_umadb_server

from eventsourcing.tests.postgres_utils import drop_tables
from examples.dcb_enrolment.test_enrolment import EnrolmentTestCase
from examples.dcb_enrolment_with_basic_objects.application import (
    EnrolmentWithBasicDcbObjects,
)


class TestEnrolmentWithBasicDcbObjects(EnrolmentTestCase):
    def test_enrolment_in_memory(self) -> None:
        self.assert_implementation(EnrolmentWithBasicDcbObjects())

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
            self.assert_implementation(EnrolmentWithBasicDcbObjects(env=env))
        finally:
            drop_tables()

    def test_enrolment_with_umadb(self) -> None:
        with temp_umadb_server() as url:
            env = {
                "PERSISTENCE_MODULE": "eventsourcing_umadb",
                "UMADB_URI": url,
            }
            self.assert_implementation(EnrolmentWithBasicDcbObjects(env=env))


del EnrolmentTestCase
