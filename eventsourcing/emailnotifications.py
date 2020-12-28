from functools import singledispatchmethod
from uuid import uuid4

from eventsourcing.aggregate import (
    Aggregate,
    BankAccount,
)
from eventsourcing.processapplication import (
    ProcessApplication,
    ProcessEvent,
)


class EmailNotification(Aggregate):
    def __init__(self, to, subject, message, **kwargs):
        super(EmailNotification, self).__init__(**kwargs)
        self.to = to
        self.subject = subject
        self.message = message

    @classmethod
    def create(cls, to, subject, message):
        return super()._create_(
            cls.Created,
            id=uuid4(),
            to=to,
            subject=subject,
            message=message,
        )

    class Created(Aggregate.Created):
        to: str
        subject: str
        message: str


class EmailNotifications(ProcessApplication):
    @singledispatchmethod
    def policy(
        self,
        domain_event: Aggregate.Event,
        process_event: ProcessEvent,
    ):
        pass

    @policy.register(BankAccount.Opened)
    def _(
        self,
        domain_event: Aggregate.Event,
        process_event: ProcessEvent,
    ):
        assert isinstance(domain_event, BankAccount.Opened)
        notification = EmailNotification.create(
            to=domain_event.email_address,
            subject="Your New Account",
            message="Dear {}, ...".format(
                domain_event.full_name
            ),
        )
        process_event.collect([notification])
