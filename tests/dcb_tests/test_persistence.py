from unittest import TestCase
from uuid import uuid4

from eventsourcing.dcb.api import DCBAppendCondition, DCBEvent, DCBQuery, DCBQueryItem
from eventsourcing.dcb.application import DCBRepository
from eventsourcing.dcb.domain import EnduringObject, Tagged
from eventsourcing.dcb.msgpack import Decision, MessagePackMapper
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
            repo.get("not-an-object", EnduringObject)


class TestDCBMapper(TestCase):
    def test_dcb_mapper(self) -> None:
        class MyDecision(Decision):
            a: int

        mapper = MessagePackMapper()
        tagged_event = Tagged(
            tags=["tag1", "tag2"],
            decision=MyDecision(a=1),
        )
        dcb_event = mapper.to_dcb_event(tagged_event)
        self.assertEqual(dcb_event.tags, tagged_event.tags)
        self.assertEqual(dcb_event.uuid, tagged_event.uuid)

        copy = mapper.to_domain_event(dcb_event)
        self.assertEqual(type(copy), Tagged)
        self.assertEqual(copy.tags, tagged_event.tags)
        self.assertEqual(copy.decision, tagged_event.decision)
        self.assertEqual(copy.uuid, tagged_event.uuid)


class TestEventStore(TestCase):
    def test_event_store(self) -> None:
        event_store = DCBEventStore(
            mapper=MessagePackMapper(), recorder=InMemoryDCBRecorder()
        )
        event_store.read()  # no args
        self.assertEqual(0, event_store.append([]))  # no events

        class MyDecision(Decision):
            a: int

        tagged_event: Tagged[Decision] = Tagged(
            tags=["tag1", "tag2"],
            decision=MyDecision(a=1),
        )
        position = event_store.append([tagged_event])
        self.assertEqual(position, 1)
        copies = list(event_store.read())
        self.assertEqual(len(copies), 1)
        copy = copies[0]

        self.assertEqual(type(copy), Tagged)
        self.assertEqual(copy.tags, tagged_event.tags)
        self.assertEqual(copy.decision, tagged_event.decision)
        self.assertEqual(copy.uuid, tagged_event.uuid)


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

    def test_unconditional_append_and_read(self) -> None:

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
            dcb_event = DCBEvent(
                type="t1", data=b'{"a": 1}', tags=["t2", "t3"], uuid=str(uuid4())
            )
            recorder.append([dcb_event])

            resp = recorder.read(DCBQuery(items=[DCBQueryItem(tags=dcb_event.tags)]))
            copies = list(resp)
            self.assertEqual(len(copies), 1)
            copy = copies[0]
            self.assertEqual(copy.event.type, dcb_event.type)
            self.assertEqual(copy.event.data, dcb_event.data)
            self.assertEqual(copy.event.tags, dcb_event.tags)
            self.assertEqual(copy.event.uuid, dcb_event.uuid)

    def test_conditional_append_and_read(self) -> None:

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
            dcb_event = DCBEvent(
                type="t1", data=b'{"a": 1}', tags=["t2", "t3"], uuid=str(uuid4())
            )
            dcb_query = DCBQuery(items=[DCBQueryItem(tags=dcb_event.tags)])
            recorder.append(
                [dcb_event],
                condition=DCBAppendCondition(fail_if_events_match=dcb_query),
            )

            resp = recorder.read(dcb_query)
            copies = list(resp)
            self.assertEqual(len(copies), 1)
            copy = copies[0]
            self.assertEqual(copy.event.type, dcb_event.type)
            self.assertEqual(copy.event.data, dcb_event.data)
            self.assertEqual(copy.event.tags, dcb_event.tags)
            self.assertEqual(copy.event.uuid, dcb_event.uuid)

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
