from functools import singledispatch
from unittest.case import TestCase

from eventsourcing.emailnotifications import (
    EmailNotification,
)
from eventsourcing.processapplication import ProcessEvent
from eventsourcing.test_aggregate import BankAccount
from eventsourcing.tracking import Tracking


@singledispatch
def policy(domain_event, process_event):
    if isinstance(domain_event, BankAccount.Created):
        notification = EmailNotification.create(
            to=domain_event.email_address,
            subject="Your New Account",
            message="Dear {}".format(
                domain_event.full_name
            ),
        )
        process_event.collect([notification])


class TestProcessingPolicy(TestCase):
    def test(self):
        # Open an account.
        account = BankAccount.open(
            full_name="Alice",
            email_address="alice@example.com",
        )
        events = account._collect_()
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
