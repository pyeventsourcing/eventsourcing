from __future__ import annotations

from typing import TYPE_CHECKING, Any, override
from unittest.case import TestCase
from uuid import NAMESPACE_URL, uuid4, uuid5

from eventsourcing import dataclasses, pydantic
from eventsourcing.application import AggregatesApplication, ProcessingEvent
from eventsourcing.decorator import triggers
from eventsourcing.errors import ProgrammingError
from eventsourcing.persistence import (
    ApplicationRecorder,
    IntegrityError,
    Notification,
    Tracking,
)
from eventsourcing.system import (
    Follower,
    Leader,
    ProcessApplication,
    PromptReceiver,
    System,
)
from eventsourcing.tests.application import BankAccountsWithPydantic
from eventsourcing.tests.bank_account_with_pydantic import BankAccountWithPydantic
from eventsourcing.utils import get_topic, resolve_topic
from tests.application_tests.test_processapplication import EmailProcess

if TYPE_CHECKING:
    from collections.abc import Sequence

    from eventsourcing.domain import AggregateEvent


system_defined_as_global = System(
    pipes=[
        [
            BankAccountsWithPydantic,
            EmailProcess,
        ],
        [AggregatesApplication],
    ]
)


class TestSystem(TestCase):
    def test_graph_nodes_and_edges(self) -> None:
        system = System(
            pipes=[
                [
                    BankAccountsWithPydantic,
                    EmailProcess,
                ],
                [AggregatesApplication],
            ]
        )
        self.assertEqual(len(system.nodes), 3)
        self.assertEqual(
            system.nodes["BankAccountsWithPydantic"],
            get_topic(BankAccountsWithPydantic),
        )
        self.assertEqual(system.nodes["EmailProcess"], get_topic(EmailProcess))
        self.assertEqual(system.nodes["Application"], get_topic(AggregatesApplication))

        self.assertEqual(system.leaders, ["BankAccountsWithPydantic"])
        self.assertEqual(system.followers, ["EmailProcess"])
        self.assertEqual(system.singles, ["Application"])

        self.assertEqual(len(system.edges), 1)
        self.assertIn(
            (
                "BankAccountsWithPydantic",
                "EmailProcess",
            ),
            system.edges,
        )

        self.assertEqual(len(system.singles), 1)

    def test_duplicate_edges_are_eliminated(self) -> None:
        system = System(
            pipes=[
                [
                    BankAccountsWithPydantic,
                    EmailProcess,
                ],
                [
                    BankAccountsWithPydantic,
                    EmailProcess,
                ],
                [AggregatesApplication],
            ]
        )
        self.assertEqual(len(system.nodes), 3)
        self.assertEqual(
            system.nodes["BankAccountsWithPydantic"],
            get_topic(BankAccountsWithPydantic),
        )
        self.assertEqual(system.nodes["EmailProcess"], get_topic(EmailProcess))
        self.assertEqual(system.nodes["Application"], get_topic(AggregatesApplication))

        self.assertEqual(system.leaders, ["BankAccountsWithPydantic"])
        self.assertEqual(system.followers, ["EmailProcess"])
        self.assertEqual(system.singles, ["Application"])

        self.assertEqual(len(system.edges), 1)
        self.assertIn(
            (
                "BankAccountsWithPydantic",
                "EmailProcess",
            ),
            system.edges,
        )

        self.assertEqual(len(system.singles), 1)

    def test_raises_type_error_not_a_follower(self) -> None:
        with self.assertRaises(TypeError) as cm:
            System(
                pipes=[
                    [
                        BankAccountsWithPydantic,
                        Leader,
                    ],
                ]
            )
        exception = cm.exception
        self.assertEqual(
            exception.args[0],
            "Not a follower class: <class 'eventsourcing.system.Leader'>",
        )

    def test_raises_type_error_not_a_processor(self) -> None:
        with self.assertRaises(TypeError) as cm:
            System(
                pipes=[
                    [
                        BankAccountsWithPydantic,
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

    def test_is_leaders_only(self) -> None:
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

    def test_leader_class(self) -> None:
        system = System(
            pipes=[
                [
                    AggregatesApplication,
                    ProcessApplication,
                    ProcessApplication,
                ],
            ]
        )
        self.assertTrue(issubclass(system.leader_cls("Application"), Leader))
        self.assertTrue(issubclass(system.leader_cls("ProcessApplication"), Leader))

    def test_system_has_topic_if_defined_as_module_attribute(self) -> None:
        system_topic = system_defined_as_global.topic
        self.assertTrue(system_topic.endswith("test_system:system_defined_as_global"))
        self.assertEqual(resolve_topic(system_topic), system_defined_as_global)

    def test_system_topic_is_none_if_defined_in_function_body(self) -> None:
        system = System([[]])
        with self.assertRaises(ProgrammingError):
            system.topic  # noqa: B018


class TestLeader(TestCase):
    def test(self) -> None:
        # Define fixture that receives prompts.
        class FollowerFixture(PromptReceiver[dataclasses.Decision]):
            def __init__(self) -> None:
                self.num_received = 0

            @override
            def receive_prompt(self, context_name: str, notification_id: int) -> None:
                self.num_received += 1

        # Test fixture is working.
        follower = FollowerFixture()
        follower.receive_prompt("Leader", 1)
        self.assertEqual(follower.num_received, 1)

        class MyAggregate(dataclasses.Aggregate):
            class Created(dataclasses.Decision):
                pass

            @triggers(Created)
            def __init__(self) -> None:
                pass

        env = {"TRANSCODER_TOPIC": get_topic(dataclasses.Transcoder)}

        # Construct leader.
        class DataclassLeader(Leader[ApplicationRecorder, dataclasses.Decision]):
            pass

        leader = DataclassLeader(env=env)
        leader.lead(follower)

        # Check follower receives a prompt when there are new events.
        leader.save(MyAggregate())
        self.assertEqual(follower.num_received, 2)

        # Check follower doesn't receive prompt when no new events.
        leader.save()
        self.assertEqual(follower.num_received, 2)


class TestFollower(TestCase):
    def test_process_event(self) -> None:
        class UUID5EmailNotification(pydantic.Aggregate):
            class Created(pydantic.Decision):
                to: str
                subject: str
                message: str

            @triggers(Created)
            def __init__(self, to: str, subject: str, message: str) -> None:
                self.to = to
                self.subject = subject
                self.message = message

            @classmethod
            def create_id(cls, to: str, *_: Any, **__: Any) -> str:
                return str(uuid5(NAMESPACE_URL, f"/emails/{to}"))

        class UUID5EmailProcess(EmailProcess):
            @override
            def policy(
                self,
                envelope: AggregateEvent[pydantic.Decision],
                processing_event: ProcessingEvent[pydantic.Decision],
            ) -> None:
                match envelope.decision:
                    case BankAccountWithPydantic.Opened(
                        full_name=full_name, email_address=email_address
                    ):
                        processing_event.collect_events(
                            UUID5EmailNotification(
                                to=email_address.address,
                                subject="Your New Account",
                                message=f"Dear {full_name}, ...",
                            )
                        )

        bank_accounts = BankAccountsWithPydantic()
        email_process = UUID5EmailProcess()

        account = BankAccountWithPydantic.open(
            full_name="Alice",
            email_address="alice@example.com",
        )

        aggregate_event = account.new_decisions[0]
        notification_id = bank_accounts.save(account)
        assert isinstance(notification_id, int)

        tracking = Tracking(bank_accounts.context_name, notification_id)

        # Process the event.
        email_process.process_event(aggregate_event, tracking)
        self.assertEqual(
            email_process.recorder.max_tracking_id(bank_accounts.context_name),
            notification_id,
        )

        # Raises IntegrityError when attempting to process the event again.
        with self.assertRaises(IntegrityError):
            email_process.process_event(aggregate_event, tracking)
        self.assertEqual(
            email_process.recorder.max_tracking_id(bank_accounts.context_name),
            notification_id,
        )

        # Create another event that will cause conflict with email processing.
        account = BankAccountWithPydantic.open(
            full_name="Alice",
            email_address="alice@example.com",
        )
        aggregate_event = account.new_decisions[0]
        notification_id = bank_accounts.save(account)
        assert isinstance(notification_id, int)

        # Process the event and expect an integrity error.
        tracking = Tracking(bank_accounts.context_name, notification_id)
        with self.assertRaises(IntegrityError):
            email_process.process_event(aggregate_event, tracking)

    def test_filter_received_notifications(self) -> None:
        class MyFollower(Follower[dataclasses.Decision]):
            topics: Sequence[str] = ()

            @override
            def policy(self, *args: Any, **kwargs: Any) -> None:
                pass

        # class MyAggregate(Aggregate[Decision]):
        #     class Created(Decision):
        #         pass
        #
        #     @triggers(Created)
        #     def __init__(self):
        #         pass
        env = {"TRANSCODER_TOPIC": get_topic(dataclasses.Transcoder)}

        follower = MyFollower(env=env)
        notifications = [
            Notification(
                id=1,
                originator_id=str(uuid4()),
                originator_version=1,
                state=b"",
                topic="topic1",
            )
        ]
        self.assertEqual(len(follower.filter_received_notifications(notifications)), 1)
        type(follower).topics = ["topic1"]
        self.assertEqual(len(follower.filter_received_notifications(notifications)), 1)
        type(follower).topics = ["topic2"]
        self.assertEqual(len(follower.filter_received_notifications(notifications)), 0)
