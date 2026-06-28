from __future__ import annotations

from unittest import TestCase
from uuid import UUID, uuid4

from eventsourcing.domain import datetime_now_with_tzinfo, event
from eventsourcing.persistence import NullTranscoder
from eventsourcing.pydantic.mapper import PydanticMapper
from eventsourcing.pydantic.mutablemodel import Aggregate, AggregateSnapshot
from eventsourcing.utils import get_topic


class MutableAggregateWithUuidIDAndEventClasses(Aggregate):
    class Snapshot(AggregateSnapshot):
        pass

    class Event(Aggregate.Event):
        pass

    class Started(Aggregate.Created):
        a: int

    class Reset(Event):
        a: int

    class Unused(Event):
        a: int

    @event(Started)
    def __init__(self, a: int) -> None:
        self.a = a

    @event(Reset)
    def reset(self, a: int) -> None:
        self.a = a


class MutableAggregateWithUuidIDAndEventNames(Aggregate):
    class Snapshot(AggregateSnapshot):
        pass

    @event("Started")
    def __init__(self, a: int) -> None:
        self.a = a

    @event("Reset")
    def reset(self, a: int) -> None:
        self.a = a


class MutableAggregateWithStrIDAndEventClasses(Aggregate[str]):
    class Snapshot(AggregateSnapshot[str]):
        pass

    class Started(Aggregate.Created[str]):
        a: int

    class Reset(Aggregate.Event[str]):
        a: int

    class Unused(Aggregate.Event[str]):
        a: int

    @event(Started)
    def __init__(self, a: int) -> None:
        self.a = a

    @event(Reset)
    def reset(self, a: int) -> None:
        self.a = a


class MutableAggregateWithStrIDAndEventNames(Aggregate[str]):
    class Snapshot(AggregateSnapshot):
        pass

    @event("Started")
    def __init__(self, a: int) -> None:
        self.a = a

    @event("Reset")
    def reset(self, a: int) -> None:
        self.a = a


class TestOrigintorIDTypes(TestCase):
    def test(self) -> None:
        self.assertIs(Aggregate[UUID].originator_id_type, UUID)
        self.assertIs(Aggregate.Event[UUID].originator_id_type, UUID)
        self.assertIs(Aggregate.Created[UUID].originator_id_type, UUID)
        # TODO: Implement the custom generic alias thing so this work.
        # self.assertIs(GenericAggregate[str].originator_id_type, str)
        # self.assertIs(GenericAggregate.Event[str].originator_id_type, str)
        # self.assertIs(GenericAggregate.Created[str].originator_id_type, str)


class TestMutableAggregateWithUuidIDAndEventClasses(TestCase):
    def setUp(self) -> None:
        self.mapper = PydanticMapper(NullTranscoder())

    def test_event(self) -> None:
        event = MutableAggregateWithUuidIDAndEventClasses.Event(
            originator_id=uuid4(),
            originator_version=2,
            timestamp=datetime_now_with_tzinfo(),
        )
        stored = self.mapper.to_stored_event(event)
        copy = self.mapper.to_domain_event(stored)
        assert isinstance(copy, MutableAggregateWithUuidIDAndEventClasses.Event)
        self.assertEqual(copy.originator_id, event.originator_id)
        self.assertIsInstance(copy.originator_id, UUID)
        self.assertEqual(copy.originator_version, event.originator_version)
        self.assertEqual(copy.timestamp, event.timestamp)
        self.assertEqual(copy.metadata, event.metadata)
        self.assertEqual(copy.event_id, event.event_id)

    def test_started(self) -> None:
        event = MutableAggregateWithUuidIDAndEventClasses.Started(
            originator_id=uuid4(),
            originator_version=2,
            originator_topic=get_topic(MutableAggregateWithUuidIDAndEventClasses),
            timestamp=datetime_now_with_tzinfo(),
            a=1,
        )
        stored = self.mapper.to_stored_event(event)
        copy = self.mapper.to_domain_event(stored)
        assert isinstance(copy, MutableAggregateWithUuidIDAndEventClasses.Started)
        self.assertEqual(copy.originator_id, event.originator_id)
        self.assertIsInstance(copy.originator_id, UUID)
        self.assertEqual(copy.originator_version, event.originator_version)
        self.assertEqual(copy.timestamp, event.timestamp)
        self.assertEqual(copy.metadata, event.metadata)
        self.assertEqual(copy.event_id, event.event_id)

    def test_reset(self) -> None:
        event = MutableAggregateWithUuidIDAndEventClasses.Reset(
            originator_id=uuid4(),
            originator_version=2,
            timestamp=datetime_now_with_tzinfo(),
            a=1,
        )

        stored = self.mapper.to_stored_event(event)
        copy = self.mapper.to_domain_event(stored)
        assert isinstance(copy, MutableAggregateWithUuidIDAndEventClasses.Reset)
        self.assertEqual(copy.originator_id, event.originator_id)
        self.assertIsInstance(copy.originator_id, UUID)
        self.assertEqual(copy.originator_version, event.originator_version)
        self.assertEqual(copy.timestamp, event.timestamp)
        self.assertEqual(copy.metadata, event.metadata)
        self.assertEqual(copy.event_id, event.event_id)

    def test_unused(self) -> None:
        event = MutableAggregateWithUuidIDAndEventClasses.Unused(
            originator_id=uuid4(),
            originator_version=2,
            timestamp=datetime_now_with_tzinfo(),
            a=1,
        )

        stored = self.mapper.to_stored_event(event)
        copy = self.mapper.to_domain_event(stored)
        assert isinstance(copy, MutableAggregateWithUuidIDAndEventClasses.Unused)
        self.assertEqual(copy.originator_id, event.originator_id)
        self.assertIsInstance(copy.originator_id, UUID)
        self.assertEqual(copy.originator_version, event.originator_version)
        self.assertEqual(copy.timestamp, event.timestamp)
        self.assertEqual(copy.metadata, event.metadata)
        self.assertEqual(copy.event_id, event.event_id)

    def test_lifecycle(self) -> None:
        agg = MutableAggregateWithUuidIDAndEventClasses(a=1)
        self.assertIsInstance(agg.id, UUID)
        self.assertEqual(agg.a, 1)
        agg.reset(a=2)
        self.assertEqual(agg.a, 2)
        events = agg.collect_events()
        for collected in events:
            self.assertEqual(collected.originator_id, agg.id)
            self.assertEqual(collected.originator_id, agg.id)
            self.assertIs(collected.originator_id_type, UUID)

    def test_snapshot(self) -> None:
        agg = MutableAggregateWithUuidIDAndEventClasses(a=1)
        snap = MutableAggregateWithUuidIDAndEventClasses.Snapshot.take(agg)
        self.assertEqual(snap.originator_id, agg.id)
        self.assertEqual(snap.originator_version, agg.version)
        self.assertEqual(snap.state["a"], agg.a)

        copy = snap.mutate(None)
        assert copy is not None
        self.assertIsInstance(copy, MutableAggregateWithUuidIDAndEventClasses)
        self.assertEqual(copy.id, agg.id)
        self.assertEqual(copy.version, agg.version)
        self.assertEqual(copy.a, agg.a)


class TestMutableAggregateWithUuidIDAndEventNames(TestCase):
    def setUp(self) -> None:
        self.mapper = PydanticMapper(NullTranscoder())

    def test_event(self) -> None:
        event = MutableAggregateWithUuidIDAndEventNames.Event(
            originator_id=uuid4(),
            originator_version=2,
            timestamp=datetime_now_with_tzinfo(),
        )
        stored = self.mapper.to_stored_event(event)
        copy = self.mapper.to_domain_event(stored)
        assert isinstance(copy, MutableAggregateWithUuidIDAndEventNames.Event)
        self.assertEqual(copy.originator_id, event.originator_id)
        self.assertIsInstance(copy.originator_id, UUID)
        self.assertEqual(copy.originator_version, event.originator_version)
        self.assertEqual(copy.timestamp, event.timestamp)
        self.assertEqual(copy.metadata, event.metadata)
        self.assertEqual(copy.event_id, event.event_id)

    def test_started(self) -> None:
        event = MutableAggregateWithUuidIDAndEventNames.Started(  # type: ignore[attr-defined]
            originator_id=uuid4(),
            originator_version=2,
            originator_topic=get_topic(MutableAggregateWithUuidIDAndEventNames),
            timestamp=datetime_now_with_tzinfo(),
            a=1,
        )
        stored = self.mapper.to_stored_event(event)
        copy = self.mapper.to_domain_event(stored)
        assert isinstance(copy, MutableAggregateWithUuidIDAndEventNames.Started)  # type: ignore[attr-defined]
        assert isinstance(copy, Aggregate.Event)
        self.assertEqual(copy.originator_id, event.originator_id)
        self.assertIsInstance(copy.originator_id, UUID)
        self.assertEqual(copy.originator_version, event.originator_version)
        self.assertEqual(copy.timestamp, event.timestamp)
        self.assertEqual(copy.metadata, event.metadata)
        self.assertEqual(copy.event_id, event.event_id)

    def test_reset(self) -> None:
        event = MutableAggregateWithUuidIDAndEventNames.Reset(  # type: ignore[attr-defined]
            originator_id=uuid4(),
            originator_version=2,
            timestamp=datetime_now_with_tzinfo(),
            a=1,
        )

        stored = self.mapper.to_stored_event(event)
        copy = self.mapper.to_domain_event(stored)
        assert isinstance(copy, MutableAggregateWithUuidIDAndEventNames.Reset)  # type: ignore[attr-defined]
        assert isinstance(copy, Aggregate.Event)
        self.assertEqual(copy.originator_id, event.originator_id)
        self.assertIsInstance(copy.originator_id, UUID)
        self.assertEqual(copy.originator_version, event.originator_version)
        self.assertEqual(copy.timestamp, event.timestamp)
        self.assertEqual(copy.metadata, event.metadata)
        self.assertEqual(copy.event_id, event.event_id)

    def test_lifecycle(self) -> None:
        agg = MutableAggregateWithUuidIDAndEventNames(a=1)
        self.assertIsInstance(agg.id, UUID)
        self.assertEqual(agg.a, 1)
        agg.reset(a=2)
        self.assertEqual(agg.a, 2)
        events = agg.collect_events()
        for collected in events:
            self.assertEqual(collected.originator_id, agg.id)
            self.assertEqual(collected.originator_id, agg.id)
            self.assertIs(collected.originator_id_type, UUID)

    def test_snapshot(self) -> None:
        agg = MutableAggregateWithUuidIDAndEventNames(a=1)
        snap = MutableAggregateWithUuidIDAndEventNames.Snapshot.take(agg)
        self.assertEqual(snap.originator_id, agg.id)
        self.assertEqual(snap.originator_version, agg.version)
        self.assertEqual(snap.state["a"], agg.a)

        copy = snap.mutate(None)
        assert copy is not None
        self.assertIsInstance(copy, MutableAggregateWithUuidIDAndEventNames)
        self.assertEqual(copy.id, agg.id)
        self.assertEqual(copy.version, agg.version)
        self.assertEqual(copy.a, agg.a)


class TestMutableAggregateWithStrIDAndEventClasses(TestCase):
    def setUp(self) -> None:
        self.mapper = PydanticMapper[str](NullTranscoder())

    def test_event(self) -> None:
        event = MutableAggregateWithStrIDAndEventClasses.Event(
            originator_id=str(uuid4()),
            originator_version=2,
            timestamp=datetime_now_with_tzinfo(),
        )
        stored = self.mapper.to_stored_event(event)
        copy = self.mapper.to_domain_event(stored)
        assert isinstance(copy, MutableAggregateWithStrIDAndEventClasses.Event)
        self.assertEqual(copy.originator_id, event.originator_id)
        self.assertIsInstance(copy.originator_id, str)
        self.assertEqual(copy.originator_version, event.originator_version)
        self.assertEqual(copy.timestamp, event.timestamp)
        self.assertEqual(copy.metadata, event.metadata)
        self.assertEqual(copy.event_id, event.event_id)

    def test_started(self) -> None:
        event = MutableAggregateWithStrIDAndEventClasses.Started(
            originator_id=str(uuid4()),
            originator_version=2,
            originator_topic=get_topic(MutableAggregateWithStrIDAndEventClasses),
            timestamp=datetime_now_with_tzinfo(),
            a=1,
        )
        stored = self.mapper.to_stored_event(event)
        copy = self.mapper.to_domain_event(stored)
        assert isinstance(copy, MutableAggregateWithStrIDAndEventClasses.Started)
        self.assertEqual(copy.originator_id, event.originator_id)
        self.assertIsInstance(copy.originator_id, str)
        self.assertEqual(copy.originator_version, event.originator_version)
        self.assertEqual(copy.timestamp, event.timestamp)
        self.assertEqual(copy.metadata, event.metadata)
        self.assertEqual(copy.event_id, event.event_id)

    def test_reset(self) -> None:
        event = MutableAggregateWithStrIDAndEventClasses.Reset(
            originator_id=str(uuid4()),
            originator_version=2,
            timestamp=datetime_now_with_tzinfo(),
            a=1,
        )

        stored = self.mapper.to_stored_event(event)
        copy = self.mapper.to_domain_event(stored)
        assert isinstance(copy, MutableAggregateWithStrIDAndEventClasses.Reset)
        self.assertEqual(copy.originator_id, event.originator_id)
        self.assertIsInstance(copy.originator_id, str)
        self.assertEqual(copy.originator_version, event.originator_version)
        self.assertEqual(copy.timestamp, event.timestamp)
        self.assertEqual(copy.metadata, event.metadata)
        self.assertEqual(copy.event_id, event.event_id)

    def test_unused(self) -> None:
        event = MutableAggregateWithStrIDAndEventClasses.Unused(
            originator_id=str(uuid4()),
            originator_version=2,
            timestamp=datetime_now_with_tzinfo(),
            a=1,
        )

        stored = self.mapper.to_stored_event(event)
        copy = self.mapper.to_domain_event(stored)
        assert isinstance(copy, MutableAggregateWithStrIDAndEventClasses.Unused)
        self.assertEqual(copy.originator_id, event.originator_id)
        self.assertIsInstance(copy.originator_id, str)
        self.assertEqual(copy.originator_version, event.originator_version)
        self.assertEqual(copy.timestamp, event.timestamp)
        self.assertEqual(copy.metadata, event.metadata)
        self.assertEqual(copy.event_id, event.event_id)

    def test_lifecycle(self) -> None:
        agg = MutableAggregateWithStrIDAndEventClasses(a=1)
        self.assertIsInstance(agg.id, str)
        self.assertEqual(agg.a, 1)
        agg.reset(a=2)
        self.assertEqual(agg.a, 2)
        events = agg.collect_events()
        for collected in events:
            self.assertEqual(collected.originator_id, agg.id)
            self.assertEqual(collected.originator_id, agg.id)
            self.assertIs(collected.originator_id_type, str)

    def test_snapshot(self) -> None:
        agg = MutableAggregateWithStrIDAndEventClasses(a=1)
        snap = MutableAggregateWithStrIDAndEventClasses.Snapshot.take(agg)
        self.assertEqual(snap.originator_id, agg.id)
        self.assertEqual(snap.originator_version, agg.version)
        self.assertEqual(snap.state["a"], agg.a)

        copy = snap.mutate(None)
        assert copy is not None
        self.assertIsInstance(copy, MutableAggregateWithStrIDAndEventClasses)
        self.assertEqual(copy.id, agg.id)
        self.assertEqual(copy.version, agg.version)
        self.assertEqual(copy.a, agg.a)


class TestMutableAggregateWithStrIDAndEventNames(TestCase):
    def setUp(self) -> None:
        self.mapper = PydanticMapper[str](NullTranscoder())

    def test_event(self) -> None:
        event = MutableAggregateWithStrIDAndEventNames.Event(
            originator_id=str(uuid4()),
            originator_version=2,
            timestamp=datetime_now_with_tzinfo(),
        )
        stored = self.mapper.to_stored_event(event)
        copy = self.mapper.to_domain_event(stored)
        assert isinstance(copy, MutableAggregateWithStrIDAndEventNames.Event)
        self.assertEqual(copy.originator_id, event.originator_id)
        self.assertIsInstance(copy.originator_id, str)
        self.assertEqual(copy.originator_version, event.originator_version)
        self.assertEqual(copy.timestamp, event.timestamp)
        self.assertEqual(copy.metadata, event.metadata)
        self.assertEqual(copy.event_id, event.event_id)

    def test_started(self) -> None:
        event = MutableAggregateWithStrIDAndEventNames.Started(  # type: ignore[attr-defined]
            originator_id=str(uuid4()),
            originator_version=2,
            originator_topic=get_topic(MutableAggregateWithStrIDAndEventNames),
            timestamp=datetime_now_with_tzinfo(),
            a=1,
        )
        stored = self.mapper.to_stored_event(event)
        copy = self.mapper.to_domain_event(stored)
        assert isinstance(copy, MutableAggregateWithStrIDAndEventNames.Started)  # type: ignore[attr-defined]
        assert isinstance(copy, Aggregate.Event), type(copy)
        self.assertEqual(copy.originator_id, event.originator_id)
        self.assertIsInstance(copy.originator_id, str)
        self.assertEqual(copy.originator_version, event.originator_version)
        self.assertEqual(copy.timestamp, event.timestamp)
        self.assertEqual(copy.metadata, event.metadata)
        self.assertEqual(copy.event_id, event.event_id)

    def test_reset(self) -> None:
        event = MutableAggregateWithStrIDAndEventNames.Reset(  # type: ignore[attr-defined]
            originator_id=str(uuid4()),
            originator_version=2,
            timestamp=datetime_now_with_tzinfo(),
            a=1,
        )

        stored = self.mapper.to_stored_event(event)
        copy = self.mapper.to_domain_event(stored)
        assert isinstance(copy, MutableAggregateWithStrIDAndEventNames.Reset)  # type: ignore[attr-defined]
        assert isinstance(copy, Aggregate.Event), type(copy)
        self.assertEqual(copy.originator_id, event.originator_id)
        self.assertIsInstance(copy.originator_id, str)
        self.assertEqual(copy.originator_version, event.originator_version)
        self.assertEqual(copy.timestamp, event.timestamp)
        self.assertEqual(copy.metadata, event.metadata)
        self.assertEqual(copy.event_id, event.event_id)

    def test_lifecycle(self) -> None:
        agg = MutableAggregateWithStrIDAndEventNames(a=1)
        self.assertIsInstance(agg.id, str)
        self.assertEqual(agg.a, 1)
        agg.reset(a=2)
        self.assertEqual(agg.a, 2)
        events = agg.collect_events()
        for collected in events:
            self.assertEqual(collected.originator_id, agg.id)
            self.assertEqual(collected.originator_id, agg.id)
            self.assertIs(collected.originator_id_type, str)

    def test_snapshot(self) -> None:
        agg = MutableAggregateWithStrIDAndEventNames(a=1)
        snap = MutableAggregateWithStrIDAndEventNames.Snapshot.take(agg)
        self.assertEqual(snap.originator_id, agg.id)
        self.assertEqual(snap.originator_version, agg.version)
        self.assertEqual(snap.state["a"], agg.a)

        copy = snap.mutate(None)
        assert copy is not None
        self.assertIsInstance(copy, MutableAggregateWithStrIDAndEventNames)
        self.assertEqual(copy.id, agg.id)
        self.assertEqual(copy.version, agg.version)
        self.assertEqual(copy.a, agg.a)
