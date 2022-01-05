from unittest.case import TestCase

from eventsourcing.application import Application, RecordingEvent
from eventsourcing.domain import Aggregate
from eventsourcing.system import (
    Follower,
    Leader,
    ProcessApplication,
    Promptable,
    System,
)
from eventsourcing.tests.application_tests.test_application_with_popo import (
    BankAccounts,
)
from eventsourcing.tests.application_tests.test_processapplication import (
    EmailProcess,
)
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
                self.num_received = 0

            def receive_recording_event(self, recording_event: RecordingEvent) -> None:
                self.num_received += 1

        # Test fixture is working.
        follower = FollowerFixture()
        follower.receive_recording_event(RecordingEvent("Leader", [], 1))
        self.assertEqual(follower.num_received, 1)

        # Construct leader.
        leader = Leader()
        leader.lead(follower)

        # Check follower receives a prompt when there are new events.
        leader.save(Aggregate())
        self.assertEqual(follower.num_received, 2)

        # Check follower doesn't receive prompt when no new events.
        leader.save()
        self.assertEqual(follower.num_received, 2)
