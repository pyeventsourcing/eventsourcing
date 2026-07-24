from __future__ import annotations

from typing import cast
from uuid import uuid4

from psycopg.types.json import Jsonb

from eventsourcing.dcb.tests import DcbRecorderTestCase
from eventsourcing.errors import ProgrammingError
from examples.dcb_enrolment_with_basic_objects.postgres_ts import PostgresDcbRecorderTS
from tests.dcb_tests.test_dcb import ConcurrentAppendTestCase, WithPostgres


class TestPostgresDcbRecorderTS(DcbRecorderTestCase, WithPostgres):
    postgres_dcb_recorder_class = PostgresDcbRecorderTS

    def test_append_read(self) -> None:
        self._test_append_read(self.recorder)

    def test_pg_type_dcb_event(self) -> None:
        # Check "dcb_event" type.
        uuid = uuid4()
        metadata = {"correlation_id": str(uuid4())}
        event = cast(PostgresDcbRecorderTS, self.recorder).construct_pg_dcb_event(
            type="EventType1",
            data=b"data",
            tags=["tag1", "tag2"],
            uuid=uuid,
            metadata=metadata,
        )
        self.assertEqual("EventType1", event.type)
        self.assertEqual(b"data", event.data)
        self.assertEqual(["tag1", "tag2"], event.tags)
        self.assertEqual(uuid, event.uuid)
        self.assertEqual(repr(Jsonb(metadata)), repr(event.metadata))

        with self.datastore.get_connection() as conn:
            result = conn.execute(
                (
                    "SELECT pg_typeof(%(dcb_event)s), "
                    "(%(dcb_event)s).type, "
                    "(%(dcb_event)s).data, "
                    "(%(dcb_event)s).tags, "
                    "(%(dcb_event)s).uuid, "
                    "(%(dcb_event)s).metadata"
                ),
                {"dcb_event": event},
            ).fetchone()

        assert result is not None
        self.assertEqual("dcb_event", result["pg_typeof"])
        self.assertEqual("EventType1", result["type"])
        self.assertEqual(b"data", result["data"])
        self.assertEqual(["tag1", "tag2"], result["tags"])
        self.assertEqual(uuid, result["uuid"])
        self.assertEqual(metadata, result["metadata"])

        with (
            self.assertRaises(ProgrammingError) as cm,
            self.datastore.get_connection() as conn,
        ):
            conn.execute(
                (
                    "SELECT pg_typeof(%(dcb_event)s), "
                    "(%(dcb_event)s).typeyyyyyyyyyyy, "
                    "(%(dcb_event)s).data, "
                    "(%(dcb_event)s).tags"
                ),
                {"dcb_event": event},
            ).fetchone()

        self.assertIn(
            'column "typeyyyyyyyyyyy" not found in data type dcb_event',
            str(cm.exception),
        )


class TestPostgresDcbRecorderStoreTSCommitOrderVsInsertOrder(
    ConcurrentAppendTestCase, WithPostgres
):
    postgres_dcb_recorder_class = PostgresDcbRecorderTS

    def test_commit_vs_insert_order(self) -> None:
        self._test_commit_vs_insert_order(self.recorder)

    def test_fail_condition_is_effective(self) -> None:
        self._test_fail_condition_is_effective(self.recorder)
