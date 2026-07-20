# from __future__ import annotations
#
# from unittest import TestCase
# from uuid import UUID, uuid4
#
# import msgspec
#
# from eventsourcing.domain import datetime_now_with_tzinfo, AggregateEvent
# from eventsourcing.msgspec import immutable
# from eventsourcing.msgspec.transcoder import MsgspecTranscoder
# from eventsourcing.persistence import AggregateEventMapper
#
# STRING_LIKE = {str, bytes, bytearray, memoryview}
#
#
# class TestImmutableModel(TestCase):
#     def setUp(self) -> None:
#         self.mapper = AggregateEventMapper(MsgspecTranscoder())
#
#     def test_domain_event_uuid(self) -> None:
#         envelope = AggregateEvent(
#             originator_id=uuid4(),
#             originator_version=2,
#             timestamp=datetime_now_with_tzinfo(),
#             a=1,
#         )
#         stored = self.mapper.to_stored_event(envelope)
#         copy = self.mapper.to_domain_event(stored)
#         assert isinstance(copy, DomainEventUuidID), type(copy)
#         self.assertEqual(copy.originator_id, envelope.originator_id)
#         self.assertEqual(copy.originator_version, envelope.originator_version)
#         self.assertEqual(copy.timestamp, envelope.timestamp)
#         self.assertEqual(copy.metadata, envelope.metadata)
#         self.assertEqual(copy.event_id, envelope.event_id)
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
#         copy = msgspec.json.decode(snapshot.state, type=ImmutableAggregateUuidID)
#         self.assertEqual(copy.id, agg.id)
#         self.assertEqual(copy.a, agg.a)
#
#
# class TestImmutableModelStrID(TestCase):
#     def setUp(self) -> None:
#         self.mapper = MsgspecMapper[str](NullTranscoder())
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
#         copy = msgspec.json.decode(snapshot.state, type=ImmutableAggregateStrID)
#         self.assertEqual(copy.id, agg.id)
#         self.assertEqual(copy.a, agg.a)
