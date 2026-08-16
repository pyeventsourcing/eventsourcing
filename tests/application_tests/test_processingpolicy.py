from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.case import TestCase

from eventsourcing.application import ProcessingEvent
from eventsourcing.decorator import triggers
from eventsourcing.persistence import Tracking
from eventsourcing.pydantic import Aggregate, Decision
from eventsourcing.tests.bank_account_with_pydantic import BankAccountWithPydantic

if TYPE_CHECKING:
    from eventsourcing.types import AggregateEventProtocol


def policy(
    envelope: AggregateEventProtocol[Decision],
    processing_event: ProcessingEvent[Decision],
) -> None:
    match envelope.decision:
        case BankAccountWithPydantic.Opened(
            email_address=email_address, full_name=full_name
        ):
            notification = EmailNotification(
                to=email_address.address,
                subject="Your New Account",
                message=f"Dear {full_name}",
            )
            processing_event.collect_events(notification)


class TestProcessingPolicy(TestCase):
    def test_policy(self) -> None:
        # Open an account.
        account = BankAccountWithPydantic.open(
            full_name="Alice",
            email_address="alice@example.com",
        )
        events = account.collect_events()
        created_event = events[0]

        processing_event = ProcessingEvent[Decision](
            tracking=Tracking(
                context_name="upstream_app",
                notification_id=5,
            )
        )

        policy(created_event, processing_event)

        self.assertEqual(len(processing_event.events), 1)
        self.assertIsInstance(
            processing_event.events[0].decision,
            EmailNotification.Created,
        )


class EmailNotification(Aggregate):
    class Created(Decision):
        to: str
        subject: str
        message: str

    @triggers(Created)
    def __init__(self, to: str, subject: str, message: str) -> None:
        self.to = to
        self.subject = subject
        self.message = message
