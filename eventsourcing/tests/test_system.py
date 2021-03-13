from datetime import datetime
from unittest.case import TestCase
from uuid import uuid4

from eventsourcing.application import Application
from eventsourcing.domain import AggregateEvent
from eventsourcing.system import (
    Follower,
    Leader,
    ProcessApplication,
    Promptable,
    System,
)
from eventsourcing.tests.test_application import BankAccounts
from eventsourcing.tests.test_processapplication import EmailNotifications
from eventsourcing.utils import get_topic


class TestSystem(TestCase):
    def test_graph(self):
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

    def test_raises_type_error_not_a_follower(self):
        with self.assertRaises(TypeError) as cm:
            System(
                pipes=[
                    [
                        BankAccounts,
                        Leader,
                    ],
                ]
            )
        exception = cm.exception
        self.assertEqual(
            exception.args[0],
            "Not a follower class: <class 'eventsourcing.system.Leader'>",
        )

    def test_raises_type_error_not_a_processor(self):
        with self.assertRaises(TypeError) as cm:
            System(
                pipes=[
                    [
                        BankAccounts,
                        Follower,
                        EmailNotifications,
                    ],
                ]
            )
        exception = cm.exception
        self.assertEqual(
            exception.args[0],
            "Not a process application class: <class 'eventsourcing.system.Follower'>",
        )

    def test_is_leaders_only(self):
        system = System(
            pipes=[
                [
                    Leader,
                    ProcessApplication,
                    ProcessApplication,
                ],
            ]
        )
        self.assertEqual(list(system.leaders_only), ["Leader"])

    def test_leader_class(self):
        system = System(
            pipes=[
                [
                    Application,
                    ProcessApplication,
                    ProcessApplication,
                ],
            ]
        )
        self.assertTrue(issubclass(system.leader_cls("Application"), Leader))
        self.assertTrue(issubclass(system.leader_cls("ProcessApplication"), Leader))


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
        leader.notify(
            [
                AggregateEvent(
                    originator_id=uuid4(),
                    originator_version=0,
                    timestamp=datetime.now(),
                )
            ]
        )
        self.assertEqual(follower.num_prompts, 2)

        # Check follower doesn't receive prompt when no new events.
        leader.notify([])
        self.assertEqual(follower.num_prompts, 2)
