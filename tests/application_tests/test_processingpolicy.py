from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.case import TestCase

from eventsourcing.application import ProcessingEvent
from eventsourcing.dataclasses.immutable import DataclassDecision
from eventsourcing.domain_new import Aggregate, triggers
from eventsourcing.persistence import Tracking
from eventsourcing.tests.bank_account_with_pydantic import BankAccountWithPydantic

if TYPE_CHECKING:
    from eventsourcing.domain_new import AggregateEvent, TDecision


def policy(
    envelope: AggregateEvent[TDecision], processing_event: ProcessingEvent
) -> None:
    match envelope.decision:
        case BankAccountWithPydantic.Opened(
            email_address=email_address, full_name=full_name
        ):
            notification = EmailNotification(
                to=email_address,
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

        processing_event = ProcessingEvent(
            tracking=Tracking(
                application_name="upstream_app",
                notification_id=5,
            )
        )

        policy(created_event, processing_event)

        self.assertEqual(len(processing_event.events), 1)
        self.assertIsInstance(
            processing_event.events[0].decision,
            EmailNotification.Created,
        )


class EmailNotification(Aggregate[DataclassDecision]):
    class Created(DataclassDecision):
        to: str
        subject: str
        message: str

    @triggers(Created)
    def __init__(self, to: str, subject: str, message: str) -> None:
        self.to = to
        self.subject = subject
        self.message = message
