from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import TestCase
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from eventsourcing.application import Application, EventSourcedLog
from eventsourcing.domain import Aggregate, DomainEvent
from eventsourcing.persistence import (
    DatetimeAsISO,
    DecimalAsStr,
    EventStore,
    JSONTranscoder,
    Mapper,
    UUIDAsHex,
)
from eventsourcing.popo import POPOAggregateRecorder

if TYPE_CHECKING:  # pragma: nocover
    from eventsourcing.utils import EnvType


class TestEventSourcedLog(TestCase):
    def test_logging_aggregate_ids(self) -> None:
        class LoggedID(DomainEvent):
            aggregate_id: UUID

        transcoder = JSONTranscoder()
        transcoder.register(UUIDAsHex())
        transcoder.register(DecimalAsStr())
        transcoder.register(DatetimeAsISO())

        event_recorder = POPOAggregateRecorder()
        event_store = EventStore(
            mapper=Mapper(transcoder=transcoder),
            recorder=event_recorder,
        )

        log: EventSourcedLog[LoggedID] = EventSourcedLog(
            events=event_store,
            originator_id=uuid5(NAMESPACE_URL, "/aggregates"),
            logged_cls=LoggedID,
        )
        id1 = uuid4()
        id2 = uuid4()
        id3 = uuid4()

        self.assertEqual(log.get_first(), None)
        self.assertEqual(log.get_last(), None)
        logged = log.trigger_event(aggregate_id=id1)
        event_store.put([logged])
        first = log.get_first()
        assert first
        self.assertEqual(first.aggregate_id, id1)
        last = log.get_last()
        assert last
        self.assertEqual(last.aggregate_id, id1)
        logged = log.trigger_event(aggregate_id=id2)
        event_store.put([logged])
        last = log.get_last()
        assert last
        self.assertEqual(last.aggregate_id, id2)
        logged = log.trigger_event(aggregate_id=id3, next_originator_version=3)
        event_store.put([logged])
        last = log.get_last()
        assert last
        self.assertEqual(last.aggregate_id, id3)
        first = log.get_first()
        assert first
        self.assertEqual(first.aggregate_id, id1)

        ids = [e.aggregate_id for e in log.get()]
        self.assertEqual(ids, [id1, id2, id3])

        ids = [e.aggregate_id for e in log.get(gt=1)]
        self.assertEqual(ids, [id2, id3])

        ids = [e.aggregate_id for e in log.get(lte=2)]
        self.assertEqual(ids, [id1, id2])

        ids = [e.aggregate_id for e in log.get(limit=1)]
        self.assertEqual(ids, [id1])

        ids = [e.aggregate_id for e in log.get(desc=True)]
        self.assertEqual(ids, [id3, id2, id1])

    def test_with_application(self) -> None:
        class LoggedID(DomainEvent):
            aggregate_id: UUID

        class MyApplication(Application):
            def __init__(self, env: EnvType | None = None) -> None:
                super().__init__(env=env)
                self.aggregate_log = EventSourcedLog(
                    events=self.events,
                    originator_id=uuid5(NAMESPACE_URL, "/aggregates"),
                    logged_cls=LoggedID,
                )

            def create_aggregate(self) -> UUID:
                aggregate = Aggregate()
                logged_id = self.aggregate_log.trigger_event(aggregate_id=aggregate.id)
                self.save(aggregate, logged_id)
                return aggregate.id

        app = MyApplication()

        self.assertEqual(app.aggregate_log.get_last(), None)

        aggregate1_id = app.create_aggregate()
        last = app.aggregate_log.get_last()
        assert last
        self.assertEqual(last.aggregate_id, aggregate1_id)

        aggregate2_id = app.create_aggregate()
        last = app.aggregate_log.get_last()
        assert last
        self.assertEqual(last.aggregate_id, aggregate2_id)

        aggregate_ids = [i.aggregate_id for i in app.aggregate_log.get()]
        self.assertEqual(aggregate_ids, [aggregate1_id, aggregate2_id])

    def test_subclasses(self) -> None:
        transcoder = JSONTranscoder()
        transcoder.register(UUIDAsHex())
        transcoder.register(DecimalAsStr())
        transcoder.register(DatetimeAsISO())

        event_recorder = POPOAggregateRecorder()
        event_store = EventStore(
            mapper=Mapper(transcoder=transcoder),
            recorder=event_recorder,
        )

        class TransactionLogEvent(DomainEvent):
            pass

        class AccountCredited(TransactionLogEvent):
            pass

        class AccountDebited(TransactionLogEvent):
            pass

        # Subclass EventSourcedLog.
        class TransactionLog(EventSourcedLog[TransactionLogEvent]):
            def account_credited(self) -> AccountCredited:
                return self._trigger_event(logged_cls=AccountCredited)

            def account_debited(self) -> AccountDebited:
                return self._trigger_event(logged_cls=AccountDebited)

        transaction_log = TransactionLog(
            events=event_store,
            originator_id=uuid5(NAMESPACE_URL, "/aggregates"),
            logged_cls=TransactionLogEvent,
        )

        account_credited = transaction_log.account_credited()
        self.assertIsInstance(account_credited, AccountCredited)

        account_debited = transaction_log.account_debited()
        self.assertIsInstance(account_debited, AccountDebited)
