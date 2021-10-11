from decimal import Decimal

from eventsourcing.domain import Aggregate
from eventsourcing.tests.asyncio_testcase import IsolatedAsyncioTestCase
from eventsourcing.tests.test_aggregate import BankAccount
from eventsourcing.tests.test_async_application_with_popo import BankAccounts


class BankAccountsWithAutomaticSnapshotting(BankAccounts):
    is_snapshotting_enabled = False
    snapshotting_intervals = {BankAccount: 5}


class TestAsyncApplicationWithAutomaticSnapshotting(IsolatedAsyncioTestCase):
    async def test(self):
        app = BankAccountsWithAutomaticSnapshotting()

        # Check snapshotting is enabled by setting snapshotting_intervals only.
        self.assertTrue(app.snapshots)

        # Open an account.
        account_id = await app.open_account("Alice", "alice@example.com")

        # Check there are no snapshots.
        snapshots = list(await app.snapshots.async_get(account_id))
        self.assertEqual(len(snapshots), 0)

        # Trigger twelve more events.
        for _ in range(12):
            await app.credit_account(account_id, Decimal("10.00"))

        # Check the account is at version 13.
        account = await app.get_account(account_id)
        self.assertEqual(account.version, 13)

        # Check snapshots have been taken at regular intervals.
        snapshots = list(await app.snapshots.async_get(account_id))
        self.assertEqual(len(snapshots), 2)
        self.assertEqual(snapshots[0].originator_version, 5)
        self.assertEqual(snapshots[1].originator_version, 10)

        # Check another type of aggregate is not snapshotted.
        aggregate = Aggregate()
        for _ in range(10):
            aggregate.trigger_event(Aggregate.Event)
        await app.async_save(aggregate)

        # Check snapshots have not been taken at regular intervals.
        snapshots = list(await app.snapshots.async_get(aggregate.id))
        self.assertEqual(len(snapshots), 0)
