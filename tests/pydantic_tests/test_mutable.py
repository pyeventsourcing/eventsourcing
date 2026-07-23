# from __future__ import annotations
#
# from typing import Any, Generic, get_args
# from unittest import TestCase
# from uuid import UUID, uuid4
#
# from typing import TypeVar, get_original_bases
#
# from eventsourcing.domain import datetime_now_with_tzinfo, event
# from eventsourcing.pydantic.mutable import (
#     PydanticAggregate,
#     SnapshotState,
# )
#
#
# class TestOrigintorIDTypes(TestCase):
#     def test(self) -> None:
#         self.assertIs(PydanticAggregate.originator_id_type, UUID)
#         self.assertIs(PydanticAggregate.Event.originator_id_type, UUID)
#         self.assertIs(PydanticAggregate.Created.originator_id_type, UUID)
#         self.assertIs(PydanticAggregate.Snapshot.originator_id_type, UUID)
#
#         class WithStrID(PydanticAggregate[str]):
#             pass
#
#         self.assertIs(WithStrID.originator_id_type, str)
#         self.assertIs(WithStrID.Event.originator_id_type, str)
#         self.assertIs(WithStrID.Created.originator_id_type, str)
#         self.assertIs(WithStrID.Snapshot.originator_id_type, str)
#
#         # TODO: Implement the custom generic alias for BaseAggreate.
#         #  - this works (class default) but [str] doesn't (still class default)
#         # self.assertIs(GenericAggregate[UUID].originator_id_type, UUID)
#         # self.assertIs(GenericAggregate[UUID].Event[UUID].originator_id_type, UUID)
#         # self.assertIs(GenericAggregate[UUID].Created[UUID].originator_id_type, UUID)
#         # self.assertIs(
#         GenericAggregate[UUID].Snapshot[UUID].originator_id_type, UUID
#         )
#         # self.assertIs(GenericAggregate[str].originator_id_type, str)
#         # self.assertIs(GenericAggregate[str].Event[str].originator_id_type, str)
#         # self.assertIs(GenericAggregate[str].Created[str].originator_id_type, str)
#
#         # TODO: This doesn't really belong here, because it is checking the types.
#         self.assertTrue(issubclass(PydanticAggregate.Snapshot, CanSnapshotAggregate))
#         self.assertFalse(issubclass(PydanticAggregate.Snapshot, CanMutateAggregate))
#
#
# class SnapshotStateWithA(SnapshotState):
#     a: int
#
#
# class MutableAggregateWithUuidIDAndEventClasses(PydanticAggregate[UUID]):
#     class Snapshot(PydanticAggregate.Snapshot[UUID]):
#         state: SnapshotStateWithA
#
#     class Started(PydanticAggregate.Created[UUID]):
#         a: int
#
#     class Reset(PydanticAggregate.Event[UUID]):
#         a: int
#
#     class Unused(PydanticAggregate.Event[UUID]):
#         a: int
#
#     @event(Started)
#     def __init__(self, a: int) -> None:
#         self.a = a
#
#     @event(Reset)
#     def reset(self, a: int) -> None:
#         self.a = a
#
#
# class MutableAggregateWithUuidIDAndEventNames(PydanticAggregate[UUID]):
#     class Snapshot(PydanticAggregate.Snapshot):
#         state: SnapshotStateWithA
#
#     @event("Started")
#     def __init__(self, a: int) -> None:
#         self.a = a
#
#     @event("Reset")
#     def reset(self, a: int) -> None:
#         self.a = a
#
#
# class MutableAggregateWithStrIDAndEventClasses(PydanticAggregate[str]):
#     class Snapshot(PydanticAggregate.Snapshot[str]):
#         state: SnapshotStateWithA
#
#     class Started(PydanticAggregate.Created[str]):
#         a: int
#
#     class Reset(PydanticAggregate.Event[str]):
#         a: int
#
#     class Unused(PydanticAggregate.Event[str]):
#         a: int
#
#     @event(Started)
#     def __init__(self, a: int) -> None:
#         self.a = a
#
#     @event(Reset)
#     def reset(self, a: int) -> None:
#         self.a = a
#
#
# class MutableAggregateWithStrIDAndEventNames(PydanticAggregate[str]):
#     class Snapshot(PydanticAggregate.Snapshot[str]):
#         state: SnapshotStateWithA
#
#     @event("Started")
#     def __init__(self, a: int) -> None:
#         self.a = a
#
#     @event("Reset")
#     def reset(self, a: int) -> None:
#         self.a = a
#
#
# _T = TypeVar(
#     "_T",
#     MutableAggregateWithUuidIDAndEventClasses,
#     MutableAggregateWithUuidIDAndEventNames,
#     MutableAggregateWithStrIDAndEventClasses,
#     MutableAggregateWithStrIDAndEventNames,
# )
#
#
# class MutableAggregateTestCase(TestCase, Generic[_T, TAggregateID]):
#     cls_under_test: type[_T]
#     expected_originator_id_type: TAggregateID
#
#     def __init_subclass__(cls, **kwargs: Any):
#         args = get_args(get_original_bases(cls)[0])
#         assert len(args) == 2, cls
#         cls.cls_under_test = args[0]
#         cls.expected_originator_id_type = args[1]
#
#     def setUp(self) -> None:
#         self.mapper = PydanticMapper(NullTranscoder())
#
#     def create_originator_id(self) -> TAggregateID:
#         if self.expected_originator_id_type is UUID:
#             return uuid4()
#         assert self.expected_originator_id_type is str
#         return str(uuid4())
#
#     def test_event(self) -> None:
#         event = self.cls_under_test.Event(
#             originator_id=self.create_originator_id(),
#             originator_version=2,
#             timestamp=datetime_now_with_tzinfo(),
#         )
#         stored = self.mapper.to_stored_event(event)
#         copy = self.mapper.to_domain_event(stored)
#         assert isinstance(copy, self.cls_under_test.Event)
#         self.assertEqual(copy.originator_id, event.originator_id)
#         self.assertIsInstance(copy.originator_id, self.expected_originator_id_type)
#         self.assertEqual(copy.originator_version, event.originator_version)
#         self.assertEqual(copy.timestamp, event.timestamp)
#         self.assertEqual(copy.metadata, event.metadata)
#         self.assertEqual(copy.event_id, event.event_id)
#
#     def test_started(self) -> None:
#         event = self.cls_under_test.Started(
#             originator_id=self.create_originator_id(),
#             originator_version=2,
#             timestamp=datetime_now_with_tzinfo(),
#             a=1,
#         )
#         stored = self.mapper.to_stored_event(event)
#         copy = self.mapper.to_domain_event(stored)
#         assert isinstance(copy, self.cls_under_test.Started)
#         self.assertEqual(copy.originator_id, event.originator_id)
#         self.assertIsInstance(copy.originator_id, self.expected_originator_id_type)
#         self.assertEqual(copy.originator_version, event.originator_version)
#         self.assertEqual(copy.timestamp, event.timestamp)
#         self.assertEqual(copy.metadata, event.metadata)
#         self.assertEqual(copy.event_id, event.event_id)
#
#     def test_reset(self) -> None:
#         event = self.cls_under_test.Reset(
#             originator_id=self.create_originator_id(),
#             originator_version=2,
#             timestamp=datetime_now_with_tzinfo(),
#             a=1,
#         )
#
#         stored = self.mapper.to_stored_event(event)
#         copy = self.mapper.to_domain_event(stored)
#         assert isinstance(copy, self.cls_under_test.Reset)
#         self.assertEqual(copy.originator_id, event.originator_id)
#         self.assertIsInstance(copy.originator_id, self.expected_originator_id_type)
#         self.assertEqual(copy.originator_version, event.originator_version)
#         self.assertEqual(copy.timestamp, event.timestamp)
#         self.assertEqual(copy.metadata, event.metadata)
#         self.assertEqual(copy.event_id, event.event_id)
#
#     def test_unused(self) -> None:
#         if type(self).__name__.endswith("Names"):
#             return
#         event = self.cls_under_test.Unused(
#             originator_id=self.create_originator_id(),
#             originator_version=2,
#             timestamp=datetime_now_with_tzinfo(),
#             a=1,
#         )
#
#         stored = self.mapper.to_stored_event(event)
#         copy = self.mapper.to_domain_event(stored)
#         assert isinstance(copy, self.cls_under_test.Unused)
#         self.assertEqual(copy.originator_id, event.originator_id)
#         self.assertIsInstance(copy.originator_id, self.expected_originator_id_type)
#         self.assertEqual(copy.originator_version, event.originator_version)
#         self.assertEqual(copy.timestamp, event.timestamp)
#         self.assertEqual(copy.metadata, event.metadata)
#         self.assertEqual(copy.event_id, event.event_id)
#
#     def test_lifecycle(self) -> None:
#         agg = self.cls_under_test(a=1)
#         self.assertIsInstance(agg.id, self.expected_originator_id_type)
#         self.assertEqual(agg.a, 1)
#         agg.reset(a=2)
#         self.assertEqual(agg.a, 2)
#         collected = agg.collect_events()
#         self.assertEqual(len(collected), 2)
#         self.assertIs(type(collected[0]), self.cls_under_test.Started)
#         self.assertEqual(collected[0].originator_id, agg.id)
#         self.assertEqual(collected[0].originator_version, 1)
#         self.assertIs(
#         collected[0].originator_id_type, self.expected_originator_id_type
#         )
#         self.assertIs(type(collected[1]), self.cls_under_test.Reset)
#         self.assertEqual(collected[1].originator_id, agg.id)
#         self.assertEqual(collected[1].originator_version, 2)
#         self.assertIs(
#           collected[1].originator_id_type, self.expected_originator_id_type
#           )
#
#         copy = self.cls_under_test.__new__(self.cls_under_test)
#         for c in collected:
#             copy = c.mutate(copy)
#         self.assertEqual(copy.id, agg.id)
#         self.assertEqual(copy.a, agg.a)
#         self.assertEqual(copy.version, agg.version)
#
#     def test_snapshot(self) -> None:
#         agg = self.cls_under_test(a=1)
#         snapshot = self.cls_under_test.Snapshot.take(agg)
#         self.assertEqual(snapshot.originator_id, agg.id)
#         self.assertEqual(snapshot.originator_version, agg.version)
#         self.assertEqual(snapshot.state.a, agg.a)
#
#         snapshot_stored = self.mapper.to_stored_event(snapshot)
#         snapshot_copy = self.mapper.to_domain_event(snapshot_stored)
#
#         copy = snapshot_copy.mutate(self.cls_under_test.__new__(self.cls_under_test))
#         assert copy is not None
#         self.assertIsInstance(copy, self.cls_under_test)
#         self.assertEqual(copy.id, agg.id)
#         self.assertEqual(copy.version, agg.version)
#         self.assertEqual(copy.a, agg.a)
#         self.assertEqual(copy.created_on, agg.created_on)
#         self.assertEqual(len(copy.collect_events()), 0)
#
#
# class TestMutableAggregateWithUuidIDAndEventClasses(
#     MutableAggregateTestCase[MutableAggregateWithUuidIDAndEventClasses, UUID]
# ):
#     pass
#
#
# class TestMutableAggregateWithUuidIDAndEventNames(
#     MutableAggregateTestCase[MutableAggregateWithUuidIDAndEventNames, UUID]
# ):
#     pass
#
#
# class TestMutableAggregateWithStrIDAndEventClasses(
#     MutableAggregateTestCase[MutableAggregateWithStrIDAndEventClasses, str]
# ):
#     pass
#
#
# class TestMutableAggregateWithStrIDAndEventNames(
#     MutableAggregateTestCase[MutableAggregateWithStrIDAndEventNames, str]
# ):
#     pass
#
#
# del MutableAggregateTestCase
