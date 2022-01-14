from unittest import TestCase
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from eventsourcing.application import Application, EventSourcedLog, LogEvent
from eventsourcing.domain import Aggregate
from eventsourcing.persistence import (
    DatetimeAsISO,
    DecimalAsStr,
    EventStore,
    JSONTranscoder,
    Mapper,
    ProgrammingError,
    UUIDAsHex,
)
from eventsourcing.popo import POPOAggregateRecorder


class TestEventSourcedLog(TestCase):
    def test_log_event_mutate_raises_programming_error(self):
        log_event = LogEvent(
            originator_id=uuid4(),
            originator_version=1,
            timestamp=LogEvent.create_timestamp(),
        )
        with self.assertRaises(ProgrammingError):
            log_event.mutate(None)

    def test_logging_aggregate_ids(self) -> None:
        class LoggedID(LogEvent):
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

        self.assertEqual(log.get_last(), None)
        logged = log.trigger_event(aggregate_id=id1)
        event_store.put([logged])
        self.assertEqual(log.get_last().aggregate_id, id1)
        logged = log.trigger_event(aggregate_id=id2)
        event_store.put([logged])
        self.assertEqual(log.get_last().aggregate_id, id2)
        logged = log.trigger_event(aggregate_id=id3, next_originator_version=3)
        event_store.put([logged])
        self.assertEqual(log.get_last().aggregate_id, id3)

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
        class LoggedID(LogEvent):
            aggregate_id: UUID

        class MyApplication(Application):
            def __init__(self, env=None) -> None:
                super().__init__(env=env)
                self.aggregate_log = EventSourcedLog(
                    events=self.events,
                    originator_id=uuid5(NAMESPACE_URL, "/aggregates"),
                    logged_cls=LoggedID,
                )

            def create_aggregate(self):
                aggregate = Aggregate()
                logged_id = self.aggregate_log.trigger_event(aggregate_id=aggregate.id)
                self.save(aggregate, logged_id)
                return aggregate.id

        app = MyApplication()

        self.assertEqual(app.aggregate_log.get_last(), None)

        aggregate1_id = app.create_aggregate()
        last = app.aggregate_log.get_last()
        self.assertIsInstance(last, app.aggregate_log.logged_cls)
        self.assertEqual(last.aggregate_id, aggregate1_id)

        aggregate2_id = app.create_aggregate()
        last = app.aggregate_log.get_last()
        self.assertIsInstance(last, app.aggregate_log.logged_cls)
        self.assertEqual(last.aggregate_id, aggregate2_id)

        aggregate_ids = [i.aggregate_id for i in app.aggregate_log.get()]
        self.assertEqual(aggregate_ids, [aggregate1_id, aggregate2_id])
