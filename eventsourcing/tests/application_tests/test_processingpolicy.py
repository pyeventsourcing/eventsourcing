from functools import singledispatch
from unittest.case import TestCase
from uuid import uuid4

from eventsourcing.domain import Aggregate
from eventsourcing.persistence import Tracking
from eventsourcing.system import ProcessingEvent
from eventsourcing.tests.domain_tests.test_aggregate import BankAccount


@singledispatch
def policy(domain_event, processing_event: ProcessingEvent):
    if isinstance(domain_event, BankAccount.Opened):
        notification = EmailNotification.create(
            to=domain_event.email_address,
            subject="Your New Account",
            message="Dear {}".format(domain_event.full_name),
        )
        processing_event.collect_events(notification)


@singledispatch
def policy_legacy_save(domain_event, processing_event: ProcessingEvent):
    if isinstance(domain_event, BankAccount.Opened):
        notification = EmailNotification.create(
            to=domain_event.email_address,
            subject="Your New Account",
            message="Dear {}".format(domain_event.full_name),
        )
        processing_event.save(notification)


class TestProcessingPolicy(TestCase):
    def test_policy(self):
        # Open an account.
        account = BankAccount.open(
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
            processing_event.events[0],
            EmailNotification.Created,
        )

    def test_legacy_save(self):
        # Open an account.
        account = BankAccount.open(
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

        policy_legacy_save(created_event, processing_event)

        self.assertEqual(len(processing_event.events), 1)
        self.assertIsInstance(
            processing_event.events[0],
            EmailNotification.Created,
        )


class EmailNotification(Aggregate):
    def __init__(self, to, subject, message):
        self.to = to
        self.subject = subject
        self.message = message

    @classmethod
    def create(cls, to, subject, message):
        return cls._create(
            cls.Created,
            id=uuid4(),
            to=to,
            subject=subject,
            message=message,
        )

    class Created(Aggregate.Created):
        to: str
        subject: str
        message: str
