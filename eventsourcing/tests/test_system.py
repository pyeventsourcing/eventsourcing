from datetime import datetime
from unittest.case import TestCase
from uuid import uuid4

from eventsourcing.domain import Aggregate
from eventsourcing.system import Leader, Promptable, System
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


class TestLeader(TestCase):

    def test(self):

        # Define fixture that receives prompts.
        class FollowerFixture(Promptable):
            def __init__(self):
                self.num_prompts = 0

            def receive_prompt(self, leader_name: str) -> None:
                self.num_prompts += 1

        # Test fixture is working.
        follower = FollowerFixture()
        follower.receive_prompt("")
        self.assertEqual(follower.num_prompts, 1)

        # Construct leader.
        leader = Leader()
        leader.lead(follower)

        # Check follower receives a prompt when there are new events.
        leader.notify([Aggregate.Event(
            originator_id=uuid4(),
            originator_version=0,
            timestamp=datetime.now()
        )])
        self.assertEqual(follower.num_prompts, 2)

        # Check follower doesn't receive prompt when no new events.
        leader.notify([])
        self.assertEqual(follower.num_prompts, 2)
