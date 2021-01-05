from datetime import datetime
from unittest.case import TestCase
from uuid import UUID, uuid4

from eventsourcing.domain import DomainEvent


class TestDomainEvent(TestCase):
    def test(self):

        # Define an 'account opened' domain event.
        class AccountOpened(DomainEvent):
            full_name: str
            timestamp: datetime

        # Create an 'account opened' event.
        event3 = AccountOpened(
            originator_id=uuid4(),
            originator_version=0,
            full_name="Alice",
            timestamp=datetime.now(),
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
            full_name="Bob",
            timestamp=datetime.now(),
        )

        # Check the attribute values of the domain event.
        assert event4.full_name == "Bob"
        assert isinstance(event4.originator_id, UUID)
        assert event4.originator_version == 1
