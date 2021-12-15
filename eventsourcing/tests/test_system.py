from typing import List
from unittest.case import TestCase
from uuid import uuid4

from eventsourcing.application import Application
from eventsourcing.persistence import Notification
from eventsourcing.system import (
    AlwaysPull,
    Follower,
    Leader,
    NeverPull,
    ProcessApplication,
    Promptable,
    PullGaps,
    System,
)
from eventsourcing.tests.test_application_with_popo import BankAccounts
from eventsourcing.tests.test_processapplication import EmailProcess
from eventsourcing.utils import get_topic


class TestSystem(TestCase):
    def test_graph(self):
        system = System(
            pipes=[
                [
                    BankAccounts,
                    EmailProcess,
                ],
                [Application],
            ]
        )
        self.assertEqual(len(system.nodes), 3)
        self.assertEqual(system.nodes["BankAccounts"], get_topic(BankAccounts))
        self.assertEqual(system.nodes["EmailProcess"], get_topic(EmailProcess))
        self.assertEqual(system.nodes["Application"], get_topic(Application))

        self.assertEqual(system.leaders, ["BankAccounts"])
        self.assertEqual(system.followers, ["EmailProcess"])
        self.assertEqual(system.singles, ["Application"])

        self.assertEqual(len(system.edges), 1)
        self.assertIn(
            (
                "BankAccounts",
                "EmailProcess",
            ),
            system.edges,
        )

        self.assertEqual(len(system.singles), 1)

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
                        EmailProcess,
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

            def receive_notifications(
                self, leader_name: str, notifications: List[Notification]
            ) -> None:
                self.num_prompts += 1

        # Test fixture is working.
        follower = FollowerFixture()
        follower.receive_notifications("", [])
        self.assertEqual(follower.num_prompts, 1)

        # Construct leader.
        leader = Leader()
        leader.lead(follower)

        # Check follower receives a prompt when there are new events.
        leader.notify(
            [
                Notification(
                    id=1,
                    originator_id=uuid4(),
                    originator_version=0,
                    topic="topic1",
                    state=b"",
                )
            ]
        )
        self.assertEqual(follower.num_prompts, 2)

        # Check follower doesn't receive prompt when no new events.
        leader.save()
        self.assertEqual(follower.num_prompts, 2)


class TestPullMode(TestCase):
    def test_always_pull(self):
        mode = AlwaysPull()
        self.assertTrue(mode.chose_to_pull(1, 1))
        self.assertTrue(mode.chose_to_pull(2, 1))

    def test_never_pull(self):
        mode = NeverPull()
        self.assertFalse(mode.chose_to_pull(1, 1))
        self.assertFalse(mode.chose_to_pull(2, 1))

    def test_pull_gaps(self):
        mode = PullGaps()
        self.assertFalse(mode.chose_to_pull(1, 1))
        self.assertTrue(mode.chose_to_pull(2, 1))
