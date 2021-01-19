try:
    from functools import singledispatchmethod
except ImportError:
    from functools import singledispatch, update_wrapper

    def singledispatchmethod(func):
        dispatcher = singledispatch(func)

        def wrapper(*args, **kw):
            return dispatcher.dispatch(args[1].__class__)(*args, **kw)
        wrapper.register = dispatcher.register
        update_wrapper(wrapper, func)
        return wrapper

from unittest.case import TestCase

from eventsourcing.domain import Aggregate
from eventsourcing.system import Leader, ProcessApplication, ProcessEvent
from eventsourcing.tests.test_aggregate import BankAccount
from eventsourcing.tests.test_application import BankAccounts
from eventsourcing.tests.test_processingpolicy import EmailNotification


class TestProcessApplication(TestCase):
    def test(self):
        leader_cls = type(
            BankAccounts.__name__,
            (BankAccounts, Leader),
            {},
        )

        accounts = leader_cls()
        notifications = EmailNotifications()
        notifications.follow(
            accounts.__class__.__name__,
            accounts.log,
        )

        section = notifications.log["1,5"]
        self.assertEqual(len(section.items), 0)

        accounts.open_account("Alice", "alice@example.com")

        notifications.pull_and_process("BankAccounts")

        section = notifications.log["1,5"]
        self.assertEqual(len(section.items), 1)

        notifications.pull_and_process("BankAccounts")

        section = notifications.log["1,5"]
        self.assertEqual(len(section.items), 1)

        accounts.lead(notifications)

        accounts.open_account("Bob", "bob@example.com")

        section = notifications.log["1,5"]
        self.assertEqual(len(section.items), 2)


class EmailNotifications(ProcessApplication):
    @singledispatchmethod
    def policy(
        self,
        domain_event: Aggregate.Event,
        process_event: ProcessEvent,
    ):
        """Default policy"""

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
            message="Dear {}, ...".format(domain_event.full_name),
        )
        process_event.collect([notification])
