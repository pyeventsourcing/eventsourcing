import time
from asyncio import get_event_loop
from decimal import Decimal
from uuid import UUID, uuid4

from eventsourcing.application import AggregateNotFound, Application
from eventsourcing.persistence import Transcoder
from eventsourcing.tests.asyncio_testcase import IsolatedAsyncioTestCase
from eventsourcing.tests.test_aggregate import BankAccount
from eventsourcing.tests.test_application_with_popo import (
    ApplicationTestCase,
    EmailAddressAsStr,
)
from eventsourcing.utils import get_topic


class TestAsyncApplicationWithPOPO(ApplicationTestCase, IsolatedAsyncioTestCase):
    expected_factory_topic = "eventsourcing.popo:Factory"

    async def asyncSetUp(self) -> None:
        get_event_loop().slow_callback_duration = 10

    async def test_async_example_application_snapshotting_not_enabled(self):
        app = BankAccounts()
        self.assertEqual(get_topic(type(app.factory)), self.expected_factory_topic)

        # Check AccountNotFound exception.
        with self.assertRaises(BankAccounts.AccountNotFoundError):
            await app.get_account(uuid4())

        # Open an account.
        account_id = await app.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Credit the account.
        await app.credit_account(account_id, Decimal("10.00"))
        await app.credit_account(account_id, Decimal("25.00"))
        await app.credit_account(account_id, Decimal("30.00"))

        # Check balance.
        self.assertEqual(
            await app.get_balance(account_id),
            Decimal("65.00"),
        )

        items = await app.log.async_select(1, 10)
        self.assertEqual(len(items), 4)

    async def test_async_example_application_snapshotting_enabled(self):
        app = BankAccounts(env={"IS_SNAPSHOTTING_ENABLED": "y"})

        self.assertEqual(get_topic(type(app.factory)), self.expected_factory_topic)

        # Check AccountNotFound exception.
        with self.assertRaises(BankAccounts.AccountNotFoundError):
            await app.get_account(uuid4())

        # Open an account.
        account_id = await app.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Credit the account.
        await app.credit_account(account_id, Decimal("10.00"))
        await app.credit_account(account_id, Decimal("25.00"))
        await app.credit_account(account_id, Decimal("30.00"))

        # Check balance.
        self.assertEqual(
            await app.get_balance(account_id),
            Decimal("65.00"),
        )

        items = await app.log.async_select(1, 10)
        self.assertEqual(len(items), 4)

        # Take snapshot (specify version).
        await app.async_take_snapshot(account_id, version=2)

        snapshots = list(await app.snapshots.async_get(account_id, desc=True, limit=1))
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].originator_version, 2)

        from_snapshot = await app.repository.async_get(account_id, version=3)
        self.assertIsInstance(from_snapshot, BankAccount)
        self.assertEqual(from_snapshot.version, 3)
        self.assertEqual(from_snapshot.balance, Decimal("35.00"))

        # Take snapshot (don't specify version).
        await app.async_take_snapshot(account_id)
        snapshots = list(await app.snapshots.async_get(account_id, desc=True, limit=1))
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].originator_version, 4)

        from_snapshot = await app.repository.async_get(account_id)
        self.assertIsInstance(from_snapshot, BankAccount)
        self.assertEqual(from_snapshot.version, 4)
        self.assertEqual(from_snapshot.balance, Decimal("65.00"))

    async def test_serial_put_performance(self):
        app = BankAccounts()

        # Open an account.
        account_id = await app.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )
        account = await app.get_account(account_id)

        async def put():
            # Credit the account.
            account.append_transaction(Decimal("10.00"))
            await app.async_save(account)

        started = time.time()

        [await put() for _ in range(self.timeit_number)]

        duration = time.time() - started

        self.print_time("serial store events", duration)

    async def test_serial_get_performance_with_snapshotting_enabled(self):
        print()
        await self._test_serial_get_performance(is_snapshotting_enabled=True)

    async def test_serial_get_performance_without_snapshotting_enabled(self):
        await self._test_serial_get_performance(is_snapshotting_enabled=False)

    async def _test_serial_get_performance(self, is_snapshotting_enabled: bool):

        app = BankAccounts(
            env={"IS_SNAPSHOTTING_ENABLED": "y" if is_snapshotting_enabled else "n"}
        )

        # Open an account.
        account_id = await app.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        async def read():
            # Get the account.
            await app.get_account(account_id)

        started = time.time()

        [await read() for _ in range(self.timeit_number)]

        duration = time.time() - started

        if is_snapshotting_enabled:
            test_label = "serial get with snapshotting"
        else:
            test_label = "serial get without snapshotting"
        self.print_time(test_label, duration)

    async def test_concurrent_put_performance(self):
        app = BankAccounts()

        # Open an account.
        account_id = await app.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        account = await app.get_account(account_id)

        async def put():
            # Credit the account.
            account.append_transaction(Decimal("10.00"))
            await app.async_save(account)

        started = time.time()

        futures = [put() for _ in range(self.timeit_number)]
        for f in futures:
            await f

        duration = time.time() - started

        self.print_time("concurrent store events", duration)

    async def test_concurrent_get_performance_with_snapshotting_enabled(self):
        print()
        await self.async_test_get_performance(is_snapshotting_enabled=True)

    async def test_concurrent_get_performance_without_snapshotting_enabled(self):
        await self.async_test_get_performance(is_snapshotting_enabled=False)

    async def async_test_get_performance(self, is_snapshotting_enabled: bool):

        app = BankAccounts(
            env={"IS_SNAPSHOTTING_ENABLED": "y" if is_snapshotting_enabled else "n"}
        )

        # Open an account.
        account_id = await app.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        async def read():
            # Get the account.
            await app.get_account(account_id)

        started = time.time()

        futures = [read() for _ in range(self.timeit_number)]
        for f in futures:
            await f

        duration = time.time() - started

        if is_snapshotting_enabled:
            test_label = "concurrent get with snapshotting"
        else:
            test_label = "concurrent get without snapshotting"
        self.print_time(test_label, duration)


class BankAccounts(Application):
    def register_transcodings(self, transcoder: Transcoder) -> None:
        super(BankAccounts, self).register_transcodings(transcoder)
        transcoder.register(EmailAddressAsStr())

    async def open_account(self, full_name, email_address):
        account = BankAccount.open(
            full_name=full_name,
            email_address=email_address,
        )
        await self.async_save(account)
        return account.id

    async def credit_account(self, account_id: UUID, amount: Decimal) -> None:
        account = await self.get_account(account_id)
        account.append_transaction(amount)
        await self.async_save(account)

    async def get_balance(self, account_id: UUID) -> Decimal:
        account = await self.get_account(account_id)
        return account.balance

    async def get_account(self, account_id: UUID) -> BankAccount:
        try:
            aggregate = await self.repository.async_get(account_id)
        except AggregateNotFound:
            raise self.AccountNotFoundError(account_id)
        else:
            if not isinstance(aggregate, BankAccount):
                raise self.AccountNotFoundError(account_id)
            return aggregate

    class AccountNotFoundError(Exception):
        pass
