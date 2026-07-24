from __future__ import annotations

from time import sleep
from unittest import TestCase
from uuid import uuid4

from eventsourcing.dcb.api import DcbAppendCondition, DcbEvent, DcbQuery, DcbQueryItem
from eventsourcing.dcb.postgres_tt import (
    PostgresDcbRecorderTT,
    PostgresDcbSubscription,
    PostgresTTDcbFactory,
)
from eventsourcing.dcb.tests import DcbRecorderTestCase
from eventsourcing.errors import ProgrammingError
from eventsourcing.postgres import PostgresDatastore
from eventsourcing.tests.postgres_utils import drop_tables
from tests.dcb_tests.test_dcb import ConcurrentAppendTestCase, WithPostgres


class TestPostgresDcbRecorderTT(DcbRecorderTestCase, WithPostgres):
    postgres_dcb_recorder_class = PostgresDcbRecorderTT
    pool_size = 2  # +1 for the subscription listen thread

    def test_append_read(self) -> None:
        self._test_append_read(self.recorder)

        # Cover case of query with no tags not being supported.
        with self.assertRaises(ProgrammingError) as cm:
            self.recorder.read(DcbQuery(items=[DcbQueryItem(types=["t1", "t2"])]))

        self.assertIn("Unsupported query", str(cm.exception))

    def test_append_subscribe(self) -> None:
        self._test_append_subscribe(self.recorder)

        # Also check subscription loop when select_limit is reached in pull loop.
        event = DcbEvent(
            type="type1", data=b"data1", tags=["tagX"], uuid=uuid4(), metadata={}
        )
        initial_position = self.recorder.append([event])
        with self.recorder.subscribe(after=initial_position) as subscription:
            assert isinstance(subscription, PostgresDcbSubscription)
            subscription.select_limit = 3
            self.recorder.append(events=([event] * 10))
            for _ in range(10):
                next(subscription)

        # Also check subscription loop when selecting zero in pull loop.
        subscribe = self.recorder.subscribe(after=initial_position)
        with subscribe:
            sleep(1)

        # Also check calling __next__ after stop().
        with self.assertRaises(StopIteration):
            subscription.__next__()

        # Also check calling __next__ after stop() after an error.
        subscription.stop()
        error = ValueError()
        subscription._thread_error = error
        with self.assertRaises(ValueError) as cm:
            subscription.__next__()
        self.assertEqual(error, cm.exception)

    def test_set_non_zero_lock_timeout(self) -> None:
        # Cover case of lock time being non-zero.
        # - involves executing some extra code
        with PostgresDatastore(
            dbname="eventsourcing",
            host="127.0.0.1",
            port="5432",
            user="eventsourcing",
            password="eventsourcing",  # noqa: S106
            lock_timeout=1,
        ) as datastore:
            recorder = PostgresDcbRecorderTT(datastore)
            recorder.create_table()
            recorder.append(
                [
                    DcbEvent(
                        type="t1",
                        data=b"",
                        tags=["t2", "t3"],
                        uuid=uuid4(),
                        metadata={},
                    )
                ],
                DcbAppendCondition(after=1),
            )


class TestPostgresTTDcbFactory(TestCase):
    def tearDown(self) -> None:
        drop_tables()

    def test_factory(self) -> None:
        env = {
            "PERSISTENCE_MODULE": "eventsourcing.postgres",
            "POSTGRES_DBNAME": "eventsourcing",
            "POSTGRES_HOST": "127.0.0.1",
            "POSTGRES_USER": "eventsourcing",
            "POSTGRES_PASSWORD": "eventsourcing",
        }
        factory = PostgresTTDcbFactory(env=env)

        # create table is false
        factory.env["CREATE_TABLE"] = "f"
        recorder = factory.dcb_recorder()
        with self.assertRaises(ProgrammingError):
            recorder.read()


class TestPostgresDcbRecorderTTCommitOrderVsInsertOrder(
    ConcurrentAppendTestCase, WithPostgres
):
    postgres_dcb_recorder_class = PostgresDcbRecorderTT

    def test_commit_vs_insert_order(self) -> None:
        self._test_commit_vs_insert_order(self.recorder)

    def test_fail_condition_is_effective(self) -> None:
        self._test_fail_condition_is_effective(self.recorder)
