import types
from typing import Any
from unittest.case import TestCase

from eventsourcing.application import ProcessingEvent
from eventsourcing.domain import AggregateEvent, EventEnvelope, TDecision
from eventsourcing.persistence import (
    IntegrityError,
    Transcoder,
)
from eventsourcing.pydantic.immutable import PydanticDecision
from eventsourcing.pydantic.transcoder import PydanticTranscoder
from eventsourcing.system import (
    Follower,
    Leader,
    ProcessApplication,
    RecordingEvent,
    RecordingEventReceiver,
)
from eventsourcing.tests.application import BankAccountsWithPydantic
from eventsourcing.tests.bank_account_with_pydantic import BankAccountWithPydantic
from tests.application_tests.test_processingpolicy import EmailNotification


class TestProcessApplication(TestCase):
    def test_pull_and_process(self) -> None:
        leader_cls = types.new_class(
            BankAccountsWithPydantic.__name__,
            (BankAccountsWithPydantic, Leader[PydanticDecision]),
        )

        accounts = leader_cls()
        email_process = EmailProcess()
        email_process.follow(
            accounts.name,
            accounts.notification_log,
        )

        section = email_process.notification_log["1,5"]
        self.assertEqual(len(section.items), 0)

        accounts.open_account("Alice", "alice@example.com")

        email_process.pull_and_process(BankAccountsWithPydantic.name)

        section = email_process.notification_log["1,5"]
        self.assertEqual(len(section.items), 1)

        # Check we have processed the first event.
        self.assertEqual(
            email_process.recorder.max_tracking_id(BankAccountsWithPydantic.name), 1
        )

        # Check reprocessing first event raises IntegrityError and changes nothing.
        with self.assertRaises(IntegrityError):
            email_process.pull_and_process(BankAccountsWithPydantic.name, start=0)
        self.assertEqual(
            email_process.recorder.max_tracking_id(BankAccountsWithPydantic.name), 1
        )

        # Check we can continue from the next position.
        email_process.pull_and_process(BankAccountsWithPydantic.name, start=1)

        # Check we haven't actually processed anything further.
        self.assertEqual(
            email_process.recorder.max_tracking_id(BankAccountsWithPydantic.name), 1
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
            email_process.recorder.max_tracking_id(BankAccountsWithPydantic.name), 2
        )


class EmailProcess(ProcessApplication[PydanticDecision]):
    def construct_transcoder(self) -> Transcoder[PydanticDecision]:
        return PydanticTranscoder()

    def policy(
        self,
        envelope: EventEnvelope[PydanticDecision],
        processing_event: ProcessingEvent[PydanticDecision],
    ) -> None:
        match envelope:
            case AggregateEvent(
                decision=BankAccountWithPydantic.Opened(
                    full_name=full_name, email_address=email_address
                )
            ):
                notification = EmailNotification(
                    to=email_address.address,
                    subject="Your New Account",
                    message=f"Dear {full_name}, ...",
                )
                processing_event.collect_events(notification)


class PromptForwarder(RecordingEventReceiver[TDecision]):
    def __init__(self, application: Follower[Any]):
        self.application = application

    def receive_recording_event(
        self, new_recording_event: RecordingEvent[TDecision]
    ) -> None:
        self.application.pull_and_process(
            leader_name=new_recording_event.application_name,
            # start=recording_event.recordings[0].notification.id,
        )
