from unittest import TestCase

from eventsourcing.dcb.api import DCBAppendCondition, DCBEvent, DCBQuery, DCBQueryItem
from eventsourcing.dcb.application import DCBRepository
from eventsourcing.dcb.msgpack import MessagePackMapper
from eventsourcing.dcb.persistence import DCBEventStore, NotFoundError
from eventsourcing.dcb.popo import InMemoryDCBRecorder
from eventsourcing.dcb.postgres_tt import PostgresDCBRecorderTT, PostgresTTDCBFactory
from eventsourcing.persistence import ProgrammingError
from eventsourcing.postgres import PostgresDatastore
from eventsourcing.tests.postgres_utils import drop_tables


class TestRepository(TestCase):
    def test_repository(self) -> None:
        repo = DCBRepository(
            DCBEventStore(mapper=MessagePackMapper(), recorder=InMemoryDCBRecorder())
        )
        with self.assertRaises(NotFoundError):
            repo.get("not-an-object")


class TestEventStore(TestCase):
    def test_event_store(self) -> None:
        event_store = DCBEventStore(
            mapper=MessagePackMapper(), recorder=InMemoryDCBRecorder()
        )
        event_store.read()  # no args
        self.assertEqual(0, event_store.append([]))  # no events


class TestInMemoryDCBRecorder(TestCase):
    def test_recorder(self) -> None:
        recorder = InMemoryDCBRecorder()
        with self.assertRaises(ProgrammingError):
            recorder.append([])  # no events


class TestPostgresDCBRecorderTT(TestCase):
    def tearDown(self) -> None:
        drop_tables()

    def test_recorder_non_zero_lock(self) -> None:

        # Cover case of lock time being non-zero.
        with PostgresDatastore(
            dbname="eventsourcing",
            host="127.0.0.1",
            port="5432",
            user="eventsourcing",
            password="eventsourcing",  # noqa: S106
            lock_timeout=1,
        ) as datastore:
            recorder = PostgresDCBRecorderTT(datastore)
            recorder.create_table()
            recorder.append(
                [DCBEvent(type="t1", data=b"", tags=["t2", "t3"])],
                DCBAppendCondition(after=1),
            )

    def test_recorder_unsupported_query(self) -> None:

        # Cover case of lock time being non-zero.
        with PostgresDatastore(
            dbname="eventsourcing",
            host="127.0.0.1",
            port="5432",
            user="eventsourcing",
            password="eventsourcing",  # noqa: S106
        ) as datastore:
            recorder = PostgresDCBRecorderTT(datastore)
            recorder.create_table()
            recorder.append([DCBEvent(type="t1", data=b"", tags=["t2", "t3"])])

            with self.assertRaises(ProgrammingError) as cm:
                recorder.read(DCBQuery(items=[DCBQueryItem(types=["t1", "t2"])]))

            self.assertIn("Unsupported query", str(cm.exception))


class TestPostgresTTDCBFactory(TestCase):
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
        factory = PostgresTTDCBFactory(env=env)

        # create table is false
        factory.env["CREATE_TABLE"] = "f"
        recorder = factory.dcb_recorder()
        with self.assertRaises(ProgrammingError):
            recorder.read()
