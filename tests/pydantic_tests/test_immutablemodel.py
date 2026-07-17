# from __future__ import annotations
#
# from unittest import TestCase
# from uuid import UUID, uuid4
#
# from eventsourcing.domain_new import datetime_now_with_tzinfo
# from eventsourcing.persistence import NullTranscoder
# from eventsourcing.pydantic import immutable
# from eventsourcing.pydantic.mapper import PydanticMapper
#
# STRING_LIKE = {str, bytes, bytearray, memoryview}
#
#
# class DomainEventUuidID(immutable.DomainEvent[UUID]):
#     a: int
#
#
# class DomainEventStrID(immutable.DomainEvent[str]):
#     a: int
#
#
# class ImmutableAggregateUuidID(immutable.ImmutablePydanticAggregate[UUID]):
#     a: int
#
#
# class ImmutableAggregateStrID(immutable.ImmutablePydanticAggregate[str]):
#     a: int
#
#
# ### Experimenting with pydantic...
#
#
# class TestImmutableModelUuidID(TestCase):
#     def setUp(self) -> None:
#         self.mapper = PydanticMapper(NullTranscoder())
#
#     def test_domain_event_uuid(self) -> None:
#         domain_event = DomainEventUuidID(
#             originator_id=uuid4(),
#             originator_version=2,
#             timestamp=datetime_now_with_tzinfo(),
#             a=1,
#         )
#         stored = self.mapper.to_stored_event(domain_event)
#         copy = self.mapper.to_domain_event(stored)
#         assert isinstance(copy, DomainEventUuidID), type(copy)
#         self.assertEqual(copy.originator_id, domain_event.originator_id)
#         self.assertEqual(copy.originator_version, domain_event.originator_version)
#         self.assertEqual(copy.timestamp, domain_event.timestamp)
#         self.assertEqual(copy.metadata, domain_event.metadata)
#         self.assertEqual(copy.event_id, domain_event.event_id)
#
#     def test_immutable_snapshot_uuid(self) -> None:
#         agg = ImmutableAggregateUuidID(
#             id=uuid4(),
#             version=0,
#             created_on=datetime_now_with_tzinfo(),
#             modified_on=datetime_now_with_tzinfo(),
#             a=1,
#         )
#         snapshot = immutable.SnapshotUuidID.take(agg)
#         copy = ImmutableAggregateUuidID.model_validate(snapshot.state)
#         self.assertEqual(copy.id, agg.id)
#         self.assertEqual(copy.a, agg.a)
#
#
# class TestImmutableModelStrID(TestCase):
#     def setUp(self) -> None:
#         self.mapper = PydanticMapper[str](NullTranscoder())
#
#     def test_domain_event_str(self) -> None:
#         domain_event = DomainEventStrID(
#             originator_id=str(uuid4()),
#             originator_version=2,
#             timestamp=datetime_now_with_tzinfo(),
#             a=1,
#         )
#         stored = self.mapper.to_stored_event(domain_event)
#         copy = self.mapper.to_domain_event(stored)
#         assert isinstance(copy, DomainEventStrID)
#         self.assertEqual(copy.originator_id, domain_event.originator_id)
#         self.assertEqual(copy.originator_version, domain_event.originator_version)
#         self.assertEqual(copy.timestamp, domain_event.timestamp)
#         self.assertEqual(copy.metadata, domain_event.metadata)
#         self.assertEqual(copy.event_id, domain_event.event_id)
#
#     def test_immutable_snaphot_str(self) -> None:
#         agg = ImmutableAggregateStrID(
#             id=str(uuid4()),
#             version=0,
#             created_on=datetime_now_with_tzinfo(),
#             modified_on=datetime_now_with_tzinfo(),
#             a=1,
#         )
#         snapshot = immutable.SnapshotStrID.take(agg)
#         copy = ImmutableAggregateStrID.model_validate(snapshot.state)
#         self.assertEqual(copy.id, agg.id)
#         self.assertEqual(copy.a, agg.a)
