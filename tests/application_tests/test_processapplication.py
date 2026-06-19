from typing import Any
from unittest.case import TestCase

from eventsourcing.application import ProcessingEvent
from eventsourcing.dispatch import singledispatchmethod
from eventsourcing.domain import DomainEventProtocol, TAggregateID
from eventsourcing.persistence import IntegrityError, JSONTranscoder
from eventsourcing.system import (
    Follower,
    Leader,
    ProcessApplication,
    RecordingEvent,
    RecordingEventReceiver,
)
from eventsourcing.tests.application import BankAccounts, EmailAddressAsStr
from eventsourcing.tests.domain import BankAccount
from tests.application_tests.test_processingpolicy import EmailNotification


class TestProcessApplication(TestCase):
    def test_pull_and_process(self) -> None:
        leader_cls = type(
            BankAccounts.__name__,
            (BankAccounts, Leader),
            {},
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

        email_process.pull_and_process(BankAccounts.name)

        section = email_process.notification_log["1,5"]
        self.assertEqual(len(section.items), 1)

        # Check we have processed the first event.
        self.assertEqual(email_process.recorder.max_tracking_id(BankAccounts.name), 1)

        # Check reprocessing first event raises IntegrityError and changes nothing.
        with self.assertRaises(IntegrityError):
            email_process.pull_and_process(BankAccounts.name, start=0)
        self.assertEqual(email_process.recorder.max_tracking_id(BankAccounts.name), 1)

        # Check we can continue from the next position.
        email_process.pull_and_process(BankAccounts.name, start=1)

        # Check we haven't actually processed anything further.
        self.assertEqual(email_process.recorder.max_tracking_id(BankAccounts.name), 1)
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
        self.assertEqual(email_process.recorder.max_tracking_id(BankAccounts.name), 2)


class EmailProcess(ProcessApplication):
    def register_transcodings(self, transcoder: JSONTranscoder) -> None:
        super().register_transcodings(transcoder)
        transcoder.register(EmailAddressAsStr())

    @singledispatchmethod
    def policy(
        self,
        domain_event: DomainEventProtocol,
        processing_event: ProcessingEvent,
    ) -> None:
        """Default policy"""

    @policy.register
    def _(
        self,
        domain_event: BankAccount.Opened,
        processing_event: ProcessingEvent,
    ) -> None:
        notification = EmailNotification.create(
            to=domain_event.email_address,
            subject="Your New Account",
            message=f"Dear {domain_event.full_name}, ...",
        )
        processing_event.collect_events(notification)


class PromptForwarder(RecordingEventReceiver[TAggregateID]):
    def __init__(self, application: Follower[Any]):
        self.application = application

    def receive_recording_event(
        self, new_recording_event: RecordingEvent[TAggregateID]
    ) -> None:
        self.application.pull_and_process(
            leader_name=new_recording_event.application_name,
            # start=recording_event.recordings[0].notification.id,
        )
