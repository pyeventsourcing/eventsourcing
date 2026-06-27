import warnings
from dataclasses import _DataclassParams, dataclass  # type: ignore[attr-defined]
from datetime import UTC, datetime, timedelta, timezone
from time import sleep
from unittest.case import TestCase
from uuid import UUID, uuid4

from typing_extensions import TypeVar

import eventsourcing.domain
from eventsourcing.domain import (
    CanInitAggregate,
    CanMutateAggregate,
    CanSnapshotAggregate,
    DomainEvent,
    HasOriginatorIDVersion,
    MetaDomainEvent,
    create_utc_datetime_now,
    datetime_now_with_tzinfo,
    event_id_from_originator_id_and_version,
)


class TestMetaDomainEvent(TestCase):
    def test_class_instance_defined_as_frozen_dataclass(self) -> None:
        class A(metaclass=MetaDomainEvent):
            pass

        self.assertIsInstance(A, type)
        self.assertTrue("__dataclass_params__" in A.__dict__)
        dataclass_params = A.__dict__["__dataclass_params__"]
        self.assertIsInstance(dataclass_params, _DataclassParams)
        self.assertTrue(dataclass_params.frozen)


class TestDomainEvent(TestCase):
    def test_domain_event_class_is_a_meta_domain_event(self) -> None:
        self.assertIsInstance(DomainEvent, MetaDomainEvent)

    def test_create_timestamp(self) -> None:
        before = datetime.now(tz=UTC)
        sleep(1e-5)
        timestamp = datetime_now_with_tzinfo()
        sleep(1e-5)
        after = datetime.now(tz=UTC)
        self.assertGreater(timestamp, before)
        self.assertGreater(after, timestamp)

    def test_domain_event_instance(self) -> None:
        originator_id = uuid4()
        originator_version = 101
        a = DomainEvent(
            originator_id=originator_id,
            originator_version=originator_version,
        )
        self.assertEqual(a.originator_id, originator_id)
        self.assertEqual(a.originator_version, originator_version)
        self.assertIsInstance(a.timestamp, datetime)
        self.assertEqual(a.metadata, {})

    def test_event_id_as_given(self) -> None:
        originator_id = uuid4()
        originator_version = 101
        event_id = uuid4()
        e = DomainEvent(
            originator_id=originator_id,
            originator_version=originator_version,
            event_id=event_id,
        )
        self.assertEqual(e.event_id, event_id)

    def test_event_id_deterministic_fallback(self) -> None:
        originator_id = uuid4()
        originator_version = 101
        expected_event_id = event_id_from_originator_id_and_version(
            originator_id, originator_version
        )
        e = DomainEvent(
            originator_id=originator_id,
            originator_version=originator_version,
        )
        self.assertEqual(e.event_id, expected_event_id)

    def test_examples(self) -> None:
        # Define an 'account opened' domain event.
        @dataclass(frozen=True, kw_only=True)
        class AccountOpened(DomainEvent):
            full_name: str

        # Create an 'account opened' event.
        event3 = AccountOpened(
            originator_id=uuid4(),
            originator_version=0,
            full_name="Alice",
        )

        self.assertEqual(event3.full_name, "Alice")
        assert isinstance(event3.originator_id, UUID)
        self.assertEqual(event3.originator_version, 0)

        # Define a 'full name updated' domain event.
        @dataclass(frozen=True, kw_only=True)
        class FullNameUpdated(DomainEvent):
            full_name: str

        # Create a 'full name updated' domain event.
        event4 = FullNameUpdated(
            originator_id=event3.originator_id,
            originator_version=1,
            full_name="Bob",
        )

        # Check the attribute values of the domain event.
        self.assertEqual(event4.full_name, "Bob")
        assert isinstance(event4.originator_id, UUID)
        self.assertEqual(event4.originator_version, 1)


class TestDatetimeNowWithTzinfo(TestCase):
    def test(self) -> None:
        # Check datetime_now_with_tzinfo() returns a datetime with tzinfo.
        timestamp = datetime_now_with_tzinfo()
        self.assertIsInstance(timestamp, datetime)
        self.assertEqual(timestamp.tzinfo, UTC)

        orig_tzinfo = eventsourcing.domain.TZINFO
        alt_tzinfo = timezone(offset=timedelta(hours=1), name="AltTimeZone")
        eventsourcing.domain.TZINFO = alt_tzinfo
        try:
            timestamp = datetime_now_with_tzinfo()
            self.assertNotEqual(timestamp.tzinfo, UTC)
            self.assertEqual(timestamp.tzinfo, alt_tzinfo)
        finally:
            eventsourcing.domain.TZINFO = orig_tzinfo

        # Verify deprecation warning for create_utc_datetime_now().
        with warnings.catch_warnings(record=True) as w:
            timestamp = create_utc_datetime_now()

        self.assertIsInstance(timestamp, datetime)
        self.assertEqual(timestamp.tzinfo, UTC)

        self.assertEqual(len(w), 1)
        self.assertIs(w[-1].category, DeprecationWarning)
        self.assertIn(
            (
                "'create_utc_datetime_now()' is deprecated, "
                "use 'datetime_now_with_tzinfo()' instead"
            ),
            str(w[-1].message),
        )


class TestOriginatorIDTypeDetection(TestCase):
    def test_hasoriginatoridversion(self) -> None:
        # self.assertIsNone(HasOriginatorIDVersion.originator_id_type)
        self.assertIs(HasOriginatorIDVersion.originator_id_type, UUID)
        self.assertIs(HasOriginatorIDVersion[UUID].originator_id_type, UUID)
        # TODO: This doesn't include the type arg... and using a
        #  WrappedGenericAlias derails the construction of event classes.
        # self.assertIs(HasOriginatorIDVersion[str].originator_id_type, str)

        # class DomainEvent(HasOriginatorIDVersion[str]):
        #     pass
        #
        # DomainEvent.originator_id_type = int
        #
        # class SubDomainEvent(DomainEvent):
        #     pass

    #
    #     print(HasOriginatorIDVersion.__parameters__)
    #     print(HasOriginatorIDVersion[TA].__parameters__)
    #     print(HasOriginatorIDVersion[int].__parameters__)
    #     # raise Exception(type(alias))

    def test_uuid(self) -> None:
        class DomainEvent(CanMutateAggregate[UUID]):
            pass

        class CustomDomainEvent(DomainEvent):
            pass

        class CreatedEvent(CanInitAggregate[UUID]):
            pass

        class CustomCreatedEvent(CreatedEvent):
            pass

        class Snapshot(CanSnapshotAggregate[UUID]):
            pass

        self.assertIs(DomainEvent.originator_id_type, UUID)
        self.assertIs(CustomDomainEvent.originator_id_type, UUID)
        self.assertIs(CreatedEvent.originator_id_type, UUID)
        self.assertIs(CustomCreatedEvent.originator_id_type, UUID)
        self.assertIs(Snapshot.originator_id_type, UUID)

    def test_str(self) -> None:
        class DomainEvent(CanMutateAggregate[str]):
            pass

        class CustomDomainEvent(DomainEvent):
            pass

        class CreatedEvent(CanInitAggregate[str]):
            pass

        class CustomCreatedEvent(CreatedEvent):
            pass

        class Snapshot(CanSnapshotAggregate[str]):
            pass

        self.assertIs(DomainEvent.originator_id_type, str)
        self.assertIs(CustomDomainEvent.originator_id_type, str)
        self.assertIs(CreatedEvent.originator_id_type, str)
        self.assertIs(CustomCreatedEvent.originator_id_type, str)
        self.assertIs(Snapshot.originator_id_type, str)

    def test_int(self) -> None:
        with self.assertRaises(TypeError) as cm:

            class _DomainEvent(CanMutateAggregate[int]):  # type: ignore[type-var]
                pass

        self.assertIn(
            "Aggregate ID type arg cannot be <class 'int'>", str(cm.exception)
        )

    def test_typevar(self) -> None:
        class Sub(HasOriginatorIDVersion[_T]):  # type: ignore[type-var]
            pass

        self.assertIsNone(Sub.originator_id_type)

    def test_detect_mismatch(self) -> None:
        class A(HasOriginatorIDVersion[UUID]):
            pass

        class B(HasOriginatorIDVersion[str]):
            pass

        with self.assertRaises(TypeError) as cm:

            class C(A, B):
                pass

        self.assertIn(
            "Conflicting originator ID types detected in bases of",
            str(cm.exception),
        )


_T = TypeVar("_T")
