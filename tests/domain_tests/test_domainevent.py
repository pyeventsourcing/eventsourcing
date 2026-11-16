# import warnings
# from dataclasses import _DataclassParams, dataclass  # type: ignore[attr-defined]
# from datetime import UTC, datetime, timedelta, timezone
# from time import sleep
# from unittest.case import TestCase
# from uuid import UUID, uuid4
#
# import eventsourcing.domain_old
# from eventsourcing import domain
# from eventsourcing.domain_old import (
#     CanInitAggregate,
#     CanMutateAggregate,
#     CanSnapshotAggregate,
#     DomainEvent,
#     HasOriginatorIDVersion,
#     MetaDomainEvent,
#     create_utc_datetime_now,
#     event_id_from_stream_id_and_version,
# )
# from eventsourcing.domain import datetime_now_with_tzinfo
#
#
# class TestMetaDomainEvent(TestCase):
#     def test_class_instance_defined_as_frozen_dataclass(self) -> None:
#         class A(metaclass=MetaDomainEvent):
#             pass
#
#         self.assertIsInstance(A, type)
#         self.assertTrue("__dataclass_params__" in A.__dict__)
#         dataclass_params = A.__dict__["__dataclass_params__"]
#         self.assertIsInstance(dataclass_params, _DataclassParams)
#         self.assertTrue(dataclass_params.frozen)
#
#
# class TestDomainEvent(TestCase):
#     def test_domain_event_class_is_a_meta_domain_event(self) -> None:
#         self.assertIsInstance(DomainEvent, MetaDomainEvent)
#
#     def test_create_timestamp(self) -> None:
#         before = datetime.now(tz=UTC)
#         sleep(1e-5)
#         timestamp = datetime_now_with_tzinfo()
#         sleep(1e-5)
#         after = datetime.now(tz=UTC)
#         self.assertGreater(timestamp, before)
#         self.assertGreater(after, timestamp)
#
#     def test_domain_event_instance(self) -> None:
#         stream_id = uuid4()
#         stream_position = 101
#         a = DomainEvent(
#             stream_id=stream_id,
#             stream_position=stream_position,
#         )
#         self.assertEqual(a.stream_id, stream_id)
#         self.assertEqual(a.stream_position, stream_position)
#         self.assertIsInstance(a.timestamp, datetime)
#         self.assertEqual(a.metadata, {})
#
#     def test_event_id_as_given(self) -> None:
#         stream_id = uuid4()
#         stream_position = 101
#         event_id = uuid4()
#         e = DomainEvent(
#             stream_id=stream_id,
#             stream_position=stream_position,
#             event_id=event_id,
#         )
#         self.assertEqual(e.event_id, event_id)
#
#     def test_event_id_deterministic_fallback(self) -> None:
#         stream_id = uuid4()
#         stream_position = 101
#         expected_event_id = event_id_from_stream_id_and_version(
#             stream_id, stream_position
#         )
#         e = DomainEvent(
#             stream_id=stream_id,
#             stream_position=stream_position,
#         )
#         self.assertEqual(e.event_id, expected_event_id)
#
#     def test_examples(self) -> None:
#         # Define an 'account opened' domain event.
#         @dataclass(frozen=True, kw_only=True)
#         class AccountOpened(DomainEvent):
#             full_name: str
#
#         # Create an 'account opened' event.
#         event3 = AccountOpened(
#             stream_id=uuid4(),
#             stream_position=0,
#             full_name="Alice",
#         )
#
#         self.assertEqual(event3.full_name, "Alice")
#         assert isinstance(event3.stream_id, UUID)
#         self.assertEqual(event3.stream_position, 0)
#
#         # Define a 'full name updated' domain event.
#         @dataclass(frozen=True, kw_only=True)
#         class FullNameUpdated(DomainEvent):
#             full_name: str
#
#         # Create a 'full name updated' domain event.
#         event4 = FullNameUpdated(
#             stream_id=event3.stream_id,
#             stream_position=1,
#             full_name="Bob",
#         )
#
#         # Check the attribute values of the domain event.
#         self.assertEqual(event4.full_name, "Bob")
#         assert isinstance(event4.stream_id, UUID)
#         self.assertEqual(event4.stream_position, 1)
#
#
# class TestDatetimeNowWithTzinfo(TestCase):
#     def test(self) -> None:
#         # Check datetime_now_with_tzinfo() returns a datetime with tzinfo.
#         timestamp = datetime_now_with_tzinfo()
#         self.assertIsInstance(timestamp, datetime)
#         self.assertEqual(timestamp.tzinfo, UTC)
#
#         orig_tzinfo = domain.TZINFO
#         alt_tzinfo = timezone(offset=timedelta(hours=1), name="AltTimeZone")
#         domain.TZINFO = alt_tzinfo
#         try:
#             timestamp = datetime_now_with_tzinfo()
#             self.assertNotEqual(timestamp.tzinfo, UTC)
#             self.assertEqual(timestamp.tzinfo, alt_tzinfo)
#         finally:
#             domain.TZINFO = orig_tzinfo
#
#         # Verify deprecation warning for create_utc_datetime_now().
#         with warnings.catch_warnings(record=True) as w:
#             timestamp = create_utc_datetime_now()
#
#         self.assertIsInstance(timestamp, datetime)
#         self.assertEqual(timestamp.tzinfo, UTC)
#
#         self.assertEqual(len(w), 1)
#         self.assertIs(w[-1].category, DeprecationWarning)
#         self.assertIn(
#             (
#                 "'create_utc_datetime_now()' is deprecated, "
#                 "use 'datetime_now_with_tzinfo()' instead"
#             ),
#             str(w[-1].message),
#         )
#
#
