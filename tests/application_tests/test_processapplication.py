import types
from typing import Any, override
from unittest.case import TestCase

from eventsourcing import pydantic
from eventsourcing.application import ProcessingEvent
from eventsourcing.domain import AggregateEvent
from eventsourcing.persistence import ApplicationRecorder, IntegrityError
from eventsourcing.pydantic import Decision, ProcessApplication, Transcoder
from eventsourcing.system import (
    Follower,
    Leader,
    PromptReceiver,
)
from eventsourcing.tests.application import BankAccountsWithPydantic
from eventsourcing.tests.bank_account_with_pydantic import BankAccountWithPydantic
from tests.application_tests.test_processingpolicy import EmailNotification


class TestProcessApplication(TestCase):
    def test_pull_and_process(self) -> None:
        leader_cls = types.new_class(
            BankAccountsWithPydantic.__name__,
            (
                BankAccountsWithPydantic,
                Leader[ApplicationRecorder, Decision],
            ),
        )

        accounts = leader_cls()
        email_process = EmailProcess()
        email_process.follow(
            accounts.context_name,
            accounts.notification_log,
        )

        section = email_process.notification_log["1,5"]
        self.assertEqual(len(section.items), 0)

        accounts.open_account("Alice", "alice@example.com")

        email_process.pull_and_process(BankAccountsWithPydantic.context_name)

        section = email_process.notification_log["1,5"]
        self.assertEqual(len(section.items), 1)

        # Check we have processed the first event.
        self.assertEqual(
            email_process.recorder.max_tracking_id(
                BankAccountsWithPydantic.context_name
            ),
            1,
        )

        # Check reprocessing first event raises IntegrityError and changes nothing.
        with self.assertRaises(IntegrityError):
            email_process.pull_and_process(
                BankAccountsWithPydantic.context_name, start=0
            )
        self.assertEqual(
            email_process.recorder.max_tracking_id(
                BankAccountsWithPydantic.context_name
            ),
            1,
        )

        # Check we can continue from the next position.
        email_process.pull_and_process(BankAccountsWithPydantic.context_name, start=1)

        # Check we haven't actually processed anything further.
        self.assertEqual(
            email_process.recorder.max_tracking_id(
                BankAccountsWithPydantic.context_name
            ),
            1,
        )
        section = email_process.notification_log["1,5"]
        self.assertEqual(len(section.items), 1)

        # Subscribe for notifications.
        accounts.lead(PromptForwarder(email_process))

        # Create another notification.
        accounts.open_account("Bob", "bob@example.com")

        # Check we have processed the next notification.
        section = email_process.notification_log["1,5"]
        self.assertEqual(len(section.items), 2)

        # Check we have actually processed the second event.
        self.assertEqual(
            email_process.recorder.max_tracking_id(
                BankAccountsWithPydantic.context_name
            ),
            2,
        )


class EmailProcess(ProcessApplication):
    @override
    def construct_transcoder(self) -> Transcoder:
        return Transcoder()

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
                notification = EmailNotification(
                    to=email_address.address,
                    subject="Your New Account",
                    message=f"Dear {full_name}, ...",
                )
                processing_event.collect_events(notification)


class PromptForwarder[TDecision](PromptReceiver[TDecision]):
    def __init__(self, application: Follower[Any]):
        self.application = application

    @override
    def receive_prompt(self, context_name: str, notification_id: int) -> None:
        self.application.pull_and_process(
            leader_name=context_name,
            # start=notification_id,  # No, so that it uses its own max tracking OD.
        )
