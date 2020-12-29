from unittest.case import TestCase

from eventsourcing.emailnotifications import (
    EmailNotifications,
)
from eventsourcing.processapplication import (
    Leader,
)
from eventsourcing.test_application import BankAccounts


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

        accounts.lead(notifications)

        accounts.open_account("Bob", "bob@example.com")

        section = notifications.log["1,5"]
        self.assertEqual(len(section.items), 2)
