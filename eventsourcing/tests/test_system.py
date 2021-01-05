from unittest.case import TestCase

from eventsourcing.system import System
from eventsourcing.tests.test_application import BankAccounts
from eventsourcing.tests.test_processapplication import EmailNotifications
from eventsourcing.utils import get_topic


class TestSystem(TestCase):
    def test(self):
        system = System(
            pipes=[
                [
                    BankAccounts,
                    EmailNotifications,
                ],
            ]
        )
        self.assertEqual(len(system.nodes), 2)
        self.assertIn(
            get_topic(BankAccounts),
            system.nodes.values(),
        )
        self.assertIn(
            get_topic(EmailNotifications),
            system.nodes.values(),
        )

        self.assertEqual(len(system.edges), 1)
        self.assertIn(
            (
                "BankAccounts",
                "EmailNotifications",
            ),
            system.edges,
        )
