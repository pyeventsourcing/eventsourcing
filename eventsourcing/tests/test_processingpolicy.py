from functools import singledispatch
from unittest.case import TestCase
from uuid import uuid4

from eventsourcing.domain import Aggregate
from eventsourcing.persistence import Tracking
from eventsourcing.system import ProcessEvent
from eventsourcing.tests.test_aggregate import BankAccount


@singledispatch
def policy(domain_event, process_event: ProcessEvent):
    if isinstance(domain_event, BankAccount.Opened):
        notification = EmailNotification.create(
            to=domain_event.email_address,
            subject="Your New Account",
            message="Dear {}".format(domain_event.full_name),
        )
        process_event.save(notification)


class TestProcessingPolicy(TestCase):
    def test(self):
        # Open an account.
        account = BankAccount.open(
            full_name="Alice",
            email_address="alice@example.com",
        )
        events = account.collect_events()
        created_event = events[0]

        process_event = ProcessEvent(
            tracking=Tracking(
                application_name="upstream_app",
                notification_id=5,
            )
        )

        policy(created_event, process_event)

        self.assertEqual(len(process_event.events), 1)
        self.assertIsInstance(
            process_event.events[0],
            EmailNotification.Created,
        )


class EmailNotification(Aggregate):
    def __init__(self, to, subject, message, **kwargs):
        super(EmailNotification, self).__init__(**kwargs)
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
