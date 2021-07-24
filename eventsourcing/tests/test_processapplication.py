from unittest.case import TestCase

from eventsourcing.dispatch import singledispatchmethod
from eventsourcing.domain import AggregateEvent
from eventsourcing.persistence import Transcoder
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
    def test(self):
        leader_cls = type(
            BankAccounts.__name__,
            (BankAccounts, Leader),
            {},
        )

        accounts = leader_cls()
        notifications = EmailNotifications()
        notifications.follow(
            accounts.__class__.__name__,
            accounts.log,
        )

        section = notifications.log["1,5"]
        self.assertEqual(len(section.items), 0)

        accounts.open_account("Alice", "alice@example.com")

        notifications.pull_and_process("BankAccounts")

        section = notifications.log["1,5"]
        self.assertEqual(len(section.items), 1)

        notifications.pull_and_process("BankAccounts")

        section = notifications.log["1,5"]
        self.assertEqual(len(section.items), 1)

        accounts.lead(PromptForwarder(notifications))

        accounts.open_account("Bob", "bob@example.com")

        section = notifications.log["1,5"]
        self.assertEqual(len(section.items), 2)


class EmailNotifications(ProcessApplication):
    def register_transcodings(self, transcoder: Transcoder) -> None:
        super(EmailNotifications, self).register_transcodings(transcoder)
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
        process_event.save(notification)


class PromptForwarder(Promptable):
    def __init__(self, application: Follower):
        self.application = application

    def receive_prompt(self, leader_name: str) -> None:
        self.application.pull_and_process(leader_name)
