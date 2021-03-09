from dataclasses import _DataclassParams
from datetime import datetime
from unittest.case import TestCase
from uuid import UUID, uuid4

from eventsourcing.domain import TZINFO, DomainEvent, MetaDomainEvent


class TestMetaDomainEvent(TestCase):
    def test_class_instance_defined_as_frozen_dataclass(self):
        class A(metaclass=MetaDomainEvent):
            pass

        self.assertIsInstance(A, type)
        self.assertTrue("__dataclass_params__" in A.__dict__)
        self.assertIsInstance(A.__dataclass_params__, _DataclassParams)
        self.assertTrue(A.__dataclass_params__.frozen)


class TestDomainEvent(TestCase):
    def test_domain_event_class_is_a_meta_domain_event(self):
        self.assertIsInstance(DomainEvent, MetaDomainEvent)

    def test_domain_event_instance(self):
        originator_id = uuid4()
        originator_version = 101
        timestamp = datetime.now()
        a = DomainEvent(
            originator_id=originator_id,
            originator_version=originator_version,
            timestamp=timestamp,
        )
        self.assertEqual(a.originator_id, originator_id)
        self.assertEqual(a.originator_version, originator_version)
        self.assertEqual(a.timestamp, timestamp)

    def test_examples(self):

        # Define an 'account opened' domain event.
        class AccountOpened(DomainEvent):
            full_name: str

        # Create an 'account opened' event.
        event3 = AccountOpened(
            originator_id=uuid4(),
            originator_version=0,
            timestamp=datetime.now(tz=TZINFO),
            full_name="Alice",
        )

        assert event3.full_name == "Alice"
        assert isinstance(event3.originator_id, UUID)
        assert event3.originator_version == 0

        # Define a 'full name updated' domain event.
        class FullNameUpdated(DomainEvent):
            full_name: str
            timestamp: datetime

        # Create a 'full name updated' domain event.
        event4 = FullNameUpdated(
            originator_id=event3.originator_id,
            originator_version=1,
            timestamp=datetime.now(tz=TZINFO),
            full_name="Bob",
        )

        # Check the attribute values of the domain event.
        assert event4.full_name == "Bob"
        assert isinstance(event4.originator_id, UUID)
        assert event4.originator_version == 1
