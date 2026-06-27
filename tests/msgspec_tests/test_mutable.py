from __future__ import annotations

from unittest import TestCase
from uuid import UUID, uuid4

from eventsourcing.domain import datetime_now_with_tzinfo, event
from eventsourcing.msgspec import mutablemodel
from eventsourcing.msgspec.mapper import MsgspecMapper
from eventsourcing.msgspec.mutablemodel import (
    AggregateSnapshotStrID,
    AggregateSnapshotUuidID,
    AggregateStrID,
    AggregateUuidID,
    GenericAggregate,
)
from eventsourcing.persistence import NullTranscoder
from eventsourcing.utils import get_topic


class TestOrigintorIDTypes(TestCase):
    def test(self) -> None:
        self.assertIs(AggregateSnapshotUuidID.originator_id_type, UUID)
        self.assertIs(AggregateSnapshotUuidID.originator_id_type, UUID)
        self.assertIs(AggregateSnapshotStrID.originator_id_type, str)
        self.assertIs(AggregateSnapshotStrID.originator_id_type, str)
        self.assertIs(AggregateUuidID.originator_id_type, UUID)
        self.assertIs(AggregateUuidID.Event.originator_id_type, UUID)
        self.assertIs(AggregateUuidID.Created.originator_id_type, UUID)
        self.assertIs(AggregateUuidID.Snapshot.originator_id_type, UUID)
        self.assertIs(AggregateStrID.originator_id_type, str)
        self.assertIs(AggregateStrID.Event.originator_id_type, str)
        self.assertIs(AggregateStrID.Created.originator_id_type, str)
        self.assertIs(AggregateStrID.Snapshot.originator_id_type, str)
        self.assertIs(GenericAggregate.originator_id_type, UUID)
        self.assertIs(GenericAggregate.Event.originator_id_type, UUID)
        self.assertIs(GenericAggregate.Created.originator_id_type, UUID)
        self.assertIs(GenericAggregate.Snapshot.originator_id_type, UUID)

        class WithStrID(GenericAggregate[str]):
            pass

        self.assertIs(WithStrID.originator_id_type, str)
        self.assertIs(WithStrID.Event.originator_id_type, str)
        self.assertIs(WithStrID.Created.originator_id_type, str)
        self.assertIs(WithStrID.Snapshot.originator_id_type, str)

        # TODO: Implement the custom generic alias for BaseAggreate.
        #  - this works (class default) but [str] doesn't (still class default)
        # self.assertIs(GenericAggregate[UUID].originator_id_type, UUID)
        # self.assertIs(GenericAggregate[UUID].Event[UUID].originator_id_type, UUID)
        # self.assertIs(GenericAggregate[UUID].Created[UUID].originator_id_type, UUID)
        # self.assertIs(GenericAggregate[UUID].Snapshot[UUID].originator_id_type, UUID)
        # self.assertIs(GenericAggregate[str].originator_id_type, str)
        # self.assertIs(GenericAggregate[str].Event[str].originator_id_type, str)
        # self.assertIs(GenericAggregate[str].Created[str].originator_id_type, str)


class MutableAggregateWithUuidIDAndEventClasses(GenericAggregate[UUID]):
    # class Snapshot(AggregateSnapshot):
    #     state: DogSnapshotState
    class Event(GenericAggregate.Event[UUID]):
        pass

    class Started(Event, GenericAggregate.Created[UUID]):
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


class MutableAggregateWithUuidIDAndEventNames(mutablemodel.AggregateUuidID):
    # class Snapshot(AggregateSnapshot):
    #     state: DogSnapshotState

    @event("Started")
    def __init__(self, a: int) -> None:
        self.a = a

    @event("Reset")
    def reset(self, a: int) -> None:
        self.a = a


class MutableAggregateWithStrIDAndEventClasses(mutablemodel.AggregateStrID):
    # class Snapshot(AggregateSnapshot):
    #     state: DogSnapshotState

    class Started(mutablemodel.AggregateStrID.Created):
        a: int

    class Reset(mutablemodel.AggregateStrID.Event):
        a: int

    class Unused(mutablemodel.AggregateStrID.Event):
        a: int

    @event(Started)
    def __init__(self, a: int) -> None:
        self.a = a

    @event(Reset)
    def reset(self, a: int) -> None:
        self.a = a


class MutableAggregateWithStrIDAndEventNames(mutablemodel.AggregateStrID):
    # class Snapshot(AggregateSnapshot):
    #     state: DogSnapshotState

    @event("Started")
    def __init__(self, a: int) -> None:
        self.a = a

    @event("Reset")
    def reset(self, a: int) -> None:
        self.a = a


class TestMutableAggregateWithUuidIDAndEventClasses(TestCase):
    def setUp(self) -> None:
        self.mapper = MsgspecMapper(NullTranscoder())

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


class TestMutableAggregateWithUuidIDAndEventNames(TestCase):
    def setUp(self) -> None:
        self.mapper = MsgspecMapper(NullTranscoder())

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
        assert isinstance(copy, AggregateUuidID.Event)
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
        assert isinstance(copy, AggregateUuidID.Event)
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


class TestMutableAggregateWithStrIDAndEventClasses(TestCase):
    def setUp(self) -> None:
        self.mapper = MsgspecMapper[str](NullTranscoder())

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


class TestMutableAggregateWithStrIDAndEventNames(TestCase):
    def setUp(self) -> None:
        self.mapper = MsgspecMapper[str](NullTranscoder())

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
        assert isinstance(copy, AggregateStrID.Event), type(copy)
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
        assert isinstance(copy, AggregateStrID.Event), type(copy)
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
