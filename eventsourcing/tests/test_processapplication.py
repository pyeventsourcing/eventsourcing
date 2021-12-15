from typing import List
from unittest.case import TestCase

from eventsourcing.dispatch import singledispatchmethod
from eventsourcing.domain import AggregateEvent
from eventsourcing.persistence import IntegrityError, Notification, Transcoder
from eventsourcing.system import (
    Follower,
    Leader,
    ProcessApplication,
    ProcessEvent,
    Promptable,
)
from eventsourcing.tests.test_aggregate import BankAccount
from eventsourcing.tests.test_application_with_popo import (
    BankAccounts,
    EmailAddressAsStr,
)
from eventsourcing.tests.test_processingpolicy import EmailNotification


class TestProcessApplication(TestCase):
    def test_pull_and_process(self):
        leader_cls = type(
            BankAccounts.__name__,
            (BankAccounts, Leader),
            {},
        )

        accounts = leader_cls()
        email_process = EmailProcess()
        email_process.follow(
            accounts.name,
            accounts.log,
        )

        section = email_process.log["1,5"]
        self.assertEqual(len(section.items), 0)

        accounts.open_account("Alice", "alice@example.com")

        email_process.pull_and_process(BankAccounts.name)

        section = email_process.log["1,5"]
        self.assertEqual(len(section.items), 1)

        # Check we have processed the first event.
        self.assertEqual(email_process.recorder.max_tracking_id(BankAccounts.name), 1)

        # Check trying to reprocess the first event causes an IntegrityError.
        with self.assertRaises(IntegrityError):
            email_process.pull_and_process(BankAccounts.name, start=1)

        # Check we can continue from the next position.
        email_process.pull_and_process(BankAccounts.name, start=2)

        # Check we haven't actually processed anything further.
        self.assertEqual(email_process.recorder.max_tracking_id(BankAccounts.name), 1)
        section = email_process.log["1,5"]
        self.assertEqual(len(section.items), 1)

        # Subscribe for notifications.
        accounts.lead(PromptForwarder(email_process))

        # Create another notification.
        accounts.open_account("Bob", "bob@example.com")

        # Check we have processed the next notification.
        section = email_process.log["1,5"]
        self.assertEqual(len(section.items), 2)

        # Check we have actually processed the second event.
        self.assertEqual(email_process.recorder.max_tracking_id(BankAccounts.name), 2)


class EmailProcess(ProcessApplication):
    def register_transcodings(self, transcoder: Transcoder) -> None:
        super(EmailProcess, self).register_transcodings(transcoder)
        transcoder.register(EmailAddressAsStr())

    @singledispatchmethod
    def policy(
        self,
        domain_event: AggregateEvent,
        process_event: ProcessEvent,
    ):
        """Default policy"""

    @policy.register(BankAccount.Opened)
    def _(
        self,
        domain_event: AggregateEvent,
        process_event: ProcessEvent,
    ):
        assert isinstance(domain_event, BankAccount.Opened)
        notification = EmailNotification.create(
            to=domain_event.email_address,
            subject="Your New Account",
            message="Dear {}, ...".format(domain_event.full_name),
        )
        process_event.collect_events(notification)


class PromptForwarder(Promptable):
    def __init__(self, application: Follower):
        self.application = application

    def receive_notifications(
        self, leader_name: str, notifications: List[Notification]
    ) -> None:
        self.application.pull_and_process(leader_name, start=notifications[0].id)
