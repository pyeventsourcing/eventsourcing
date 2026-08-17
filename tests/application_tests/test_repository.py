from __future__ import annotations

from decimal import Decimal
from functools import reduce
from typing import TYPE_CHECKING, Any, cast
from unittest.case import TestCase
from uuid import uuid4

from eventsourcing.application import (
    AggregateNotFoundError,
    Cache,
    LRUCache,
    Repository,
)
from eventsourcing.persistence import (
    AggregateEventMapper,
    EventStore,
)
from eventsourcing.popo import POPOAggregateRecorder
from eventsourcing.pydantic import Decision, Transcoder
from eventsourcing.sqlite import SQLiteAggregateRecorder, SQLiteDatastore
from eventsourcing.tests.bank_account_with_pydantic import (
    BankAccountWithPydantic,
)
from eventsourcing.types import StateMutatorProtocol

if TYPE_CHECKING:
    from collections.abc import Iterable

    from eventsourcing.types import AggregateEventProtocol


class TestRepository(TestCase):
    def test_get(self) -> None:
        repository = Repository[Decision](
            EventStore(
                mapper=AggregateEventMapper(transcoder=Transcoder()),
                recorder=POPOAggregateRecorder(),
            )
        )

        aggregate = BankAccountWithPydantic.open(
            full_name="Phil",
            email_address="phil@example.com",
        )
        repository.event_store.put(aggregate.collect_events())

        copy = repository.get(aggregate.id, BankAccountWithPydantic)
        self.assertEqual(copy, aggregate)

    def test_with_snapshot_store(self) -> None:
        event_recorder = SQLiteAggregateRecorder(SQLiteDatastore(":memory:"))
        event_recorder.create_table()
        event_store = EventStore[Decision](
            mapper=AggregateEventMapper(transcoder=(Transcoder())),
            recorder=event_recorder,
        )
        snapshot_recorder = SQLiteAggregateRecorder(SQLiteDatastore(":memory:"))
        snapshot_recorder.create_table()
        snapshot_store = EventStore[Decision](
            mapper=AggregateEventMapper(transcoder=(Transcoder())),
            recorder=snapshot_recorder,
        )
        repository = Repository(event_store, snapshot_store=snapshot_store)

        # Check key error.
        with self.assertRaises(AggregateNotFoundError):
            repository.get(str(uuid4()), BankAccountWithPydantic)

        # Open an account.
        account = BankAccountWithPydantic.open(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Credit the account.
        account.append_transaction(Decimal("10.00"))
        account.append_transaction(Decimal("25.00"))
        account.append_transaction(Decimal("30.00"))

        # Collect pending events.
        pending = account.collect_events()

        # Store pending events.
        event_store.put(pending)

        copy = repository.get(account.id, BankAccountWithPydantic)
        assert isinstance(copy, BankAccountWithPydantic)
        # Check copy has correct attribute values.
        assert copy.id == account.id
        assert copy.balance == Decimal("65.00")

        snapshot_store.put([BankAccountWithPydantic.Snapshot.take(account)])

        copy2 = repository.get(account.id, BankAccountWithPydantic)
        assert isinstance(copy2, BankAccountWithPydantic)

        # Check copy has correct attribute values.
        assert copy2.id == account.id
        assert copy2.balance == Decimal("65.00")

        # Credit the account.
        account.append_transaction(Decimal("10.00"))
        event_store.put(account.collect_events())

        # Check copy has correct attribute values.
        copy3 = repository.get(account.id, BankAccountWithPydantic)
        assert isinstance(copy3, BankAccountWithPydantic)

        assert copy3.id == account.id
        assert copy3.balance == Decimal("75.00")

        # Check can get old version of account.
        copy4 = repository.get(
            account.id, BankAccountWithPydantic, version=copy.version
        )
        assert isinstance(copy4, BankAccountWithPydantic)
        assert copy4.balance == Decimal("65.00")

        copy5 = repository.get(account.id, BankAccountWithPydantic, version=1)
        assert isinstance(copy5, BankAccountWithPydantic)
        assert copy5.balance == Decimal("0.00")

        copy6 = repository.get(account.id, BankAccountWithPydantic, version=2)
        assert isinstance(copy6, BankAccountWithPydantic)
        assert copy6.balance == Decimal("10.00")

        copy7 = repository.get(account.id, BankAccountWithPydantic, version=3)
        assert isinstance(copy7, BankAccountWithPydantic)
        assert copy7.balance == Decimal("35.00"), copy7.balance

        copy8 = repository.get(account.id, BankAccountWithPydantic, version=4)
        assert isinstance(copy8, BankAccountWithPydantic)
        assert copy8.balance == Decimal("65.00"), copy8.balance

        # # Check the __getitem__ method is working
        # copy9 = repository[account.uuid]
        # self.assertEqual(copy9.balance, Decimal("75.00"))
        #
        # copy10 = repository[account.uuid, 3]
        # # assert isinstance(copy7, BankAccount)
        #
        # self.assertEqual(copy10.balance, Decimal("35.00"))

    def test_without_snapshot_store(self) -> None:
        event_recorder = SQLiteAggregateRecorder(SQLiteDatastore(":memory:"))
        event_recorder.create_table()
        event_store = EventStore[Decision](
            mapper=AggregateEventMapper(transcoder=(Transcoder())),
            recorder=event_recorder,
        )
        repository = Repository(event_store)

        # Check key error.
        with self.assertRaises(AggregateNotFoundError):
            repository.get(str(uuid4()), BankAccountWithPydantic)

        # Open an account.
        account = BankAccountWithPydantic.open(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Credit the account.
        account.append_transaction(Decimal("10.00"))
        account.append_transaction(Decimal("25.00"))
        account.append_transaction(Decimal("30.00"))

        # Collect pending events.
        pending = account.collect_events()

        # Store pending events.
        event_store.put(pending)

        copy = repository.get(account.id, BankAccountWithPydantic)
        assert isinstance(copy, BankAccountWithPydantic)
        # Check copy has correct attribute values.
        assert copy.id == account.id
        assert copy.balance == Decimal("65.00")

        # Credit the account.
        account.append_transaction(Decimal("10.00"))
        event_store.put(account.collect_events())

        # Check copy has correct attribute values.
        copy2 = repository.get(account.id, BankAccountWithPydantic)
        assert isinstance(copy2, BankAccountWithPydantic)

        assert copy2.id == account.id
        assert copy2.balance == Decimal("75.00")

        # Check can get old version of account.
        copy3 = repository.get(
            account.id, BankAccountWithPydantic, version=copy.version
        )
        assert isinstance(copy3, BankAccountWithPydantic)
        assert copy3.balance == Decimal("65.00")

        copy4 = repository.get(account.id, BankAccountWithPydantic, version=1)
        assert isinstance(copy4, BankAccountWithPydantic)
        assert copy4.balance == Decimal("0.00")

        copy5 = repository.get(account.id, BankAccountWithPydantic, version=2)
        assert isinstance(copy5, BankAccountWithPydantic)
        assert copy5.balance == Decimal("10.00")

        copy6 = repository.get(account.id, BankAccountWithPydantic, version=3)
        assert isinstance(copy6, BankAccountWithPydantic)
        assert copy6.balance == Decimal("35.00"), copy6.balance

        copy7 = repository.get(account.id, BankAccountWithPydantic, version=4)
        assert isinstance(copy7, BankAccountWithPydantic)
        assert copy7.balance == Decimal("65.00"), copy7.balance

    def test_with_alternative_mutator_function(self) -> None:
        def bank_account_projector(
            initial: BankAccountWithPydantic | None,
            envelopes: Iterable[AggregateEventProtocol[Decision]],
        ) -> BankAccountWithPydantic | None:
            if initial is None:
                initial = BankAccountWithPydantic.__new__(BankAccountWithPydantic)

            def evolve(state: Any, event: AggregateEventProtocol[Any]) -> Any:
                return cast(StateMutatorProtocol, event).mutate(state)

            return reduce(
                evolve,
                envelopes,
                cast(BankAccountWithPydantic | None, initial),
            )

        transcoder = Transcoder()

        event_recorder = SQLiteAggregateRecorder(SQLiteDatastore(":memory:"))
        event_recorder.create_table()
        event_store = EventStore[Decision](
            mapper=AggregateEventMapper(transcoder=transcoder),
            recorder=event_recorder,
        )
        snapshot_recorder = SQLiteAggregateRecorder(SQLiteDatastore(":memory:"))
        snapshot_recorder.create_table()
        snapshot_store = EventStore[Decision](
            mapper=AggregateEventMapper(transcoder=transcoder),
            recorder=snapshot_recorder,
        )
        repository = Repository[Decision](event_store, snapshot_store=snapshot_store)

        # Check key error.
        with self.assertRaises(AggregateNotFoundError):
            repository.get(str(uuid4()), BankAccountWithPydantic)

        # Open an account.
        account = BankAccountWithPydantic.open(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Credit the account.
        account.append_transaction(Decimal("10.00"))
        account.append_transaction(Decimal("25.00"))
        account.append_transaction(Decimal("30.00"))

        # Collect pending events.
        pending = account.collect_events()

        # Store pending events.
        event_store.put(pending)

        copy: BankAccountWithPydantic = repository.get(
            account.id, projector=bank_account_projector
        )

        assert isinstance(copy, BankAccountWithPydantic)
        # Check copy has correct attribute values.
        assert copy.id == account.id
        assert copy.balance == Decimal("65.00")

        snapshot_store.put([BankAccountWithPydantic.Snapshot.take(account)])

        copy2 = repository.get(account.id, projector=bank_account_projector)
        assert isinstance(copy2, BankAccountWithPydantic)

        # Check copy has correct attribute values.
        assert copy2.id == account.id
        assert copy2.balance == Decimal("65.00")

        # Credit the account.
        account.append_transaction(Decimal("10.00"))
        event_store.put(account.collect_events())

        # Check copy has correct attribute values.
        copy3 = repository.get(account.id, projector=bank_account_projector)
        assert isinstance(copy3, BankAccountWithPydantic)

        assert copy3.id == account.id
        assert copy3.balance == Decimal("75.00")

        # Check can get old version of account.
        copy4 = repository.get(
            account.id, projector=bank_account_projector, version=copy.version
        )

        assert isinstance(copy4, BankAccountWithPydantic)
        assert copy4.balance == Decimal("65.00")

        copy5 = repository.get(account.id, projector=bank_account_projector, version=1)
        assert isinstance(copy5, BankAccountWithPydantic)
        assert copy5.balance == Decimal("0.00")

        copy6 = repository.get(account.id, projector=bank_account_projector, version=2)
        assert isinstance(copy6, BankAccountWithPydantic)
        assert copy6.balance == Decimal("10.00")

        copy7 = repository.get(account.id, projector=bank_account_projector, version=3)
        assert isinstance(copy7, BankAccountWithPydantic)
        assert copy7.balance == Decimal("35.00"), copy7.balance

        copy8 = repository.get(account.id, projector=bank_account_projector, version=4)
        assert isinstance(copy8, BankAccountWithPydantic)
        assert copy8.balance == Decimal("65.00"), copy8.balance

    # TODO: We can't do this unless `item` has either a class or a projector function?
    # def test_contains(self) -> None:
    #     transcoder = JSONTranscoder()
    #     transcoder.register(UUIDAsHex())
    #     transcoder.register(DecimalAsStr())
    #     transcoder.register(DatetimeAsISO())
    #
    #     event_recorder = POPOAggregateRecorder()
    #     event_store = EventStore(
    #         mapper=DataclassMapper(transcoder=transcoder),
    #         recorder=event_recorder,
    #     )
    #
    #     aggregate = Aggregate()
    #     event_store.put(aggregate.collect_events())
    #
    #     repository = Repository(event_store)
    #     self.assertTrue(aggregate.id in repository)
    #     self.assertFalse(uuid4() in repository)

    def test_cache_maxsize_zero(self) -> None:
        transcoder = Transcoder()

        event_recorder = SQLiteAggregateRecorder(SQLiteDatastore(":memory:"))
        event_recorder.create_table()
        event_store = EventStore[Decision](
            mapper=AggregateEventMapper(transcoder=transcoder),
            recorder=event_recorder,
        )

        repository = Repository(event_store, cache_maxsize=0)

        self.assertEqual(type(repository.cache), Cache)

        account = BankAccountWithPydantic.open(
            full_name="Phil", email_address="phil@example.com"
        )

        with self.assertRaises(AggregateNotFoundError):
            repository.get(account.id, BankAccountWithPydantic)
        event_store.put(account.collect_events())
        copy = repository.get(account.id, BankAccountWithPydantic)
        self.assertEqual(copy, account)

        reconstructed1 = repository.get(account.id, BankAccountWithPydantic)
        self.assertEqual(1, reconstructed1.version)

        account.append_transaction(Decimal("10.00"))
        event_store.put(account.collect_events())
        reconstructed2 = repository.get(account.id, BankAccountWithPydantic)
        self.assertEqual(2, reconstructed2.version)

    def test_cache_maxsize_nonzero(self) -> None:
        transcoder = Transcoder()

        event_recorder = SQLiteAggregateRecorder(SQLiteDatastore(":memory:"))
        event_recorder.create_table()
        event_store = EventStore[Decision](
            mapper=AggregateEventMapper(transcoder=transcoder),
            recorder=event_recorder,
        )
        repository = Repository(event_store, cache_maxsize=2)
        self.assertEqual(type(repository.cache), LRUCache)

        aggregate1 = BankAccountWithPydantic.open(
            full_name="Phil", email_address="phil@example.com"
        )

        with self.assertRaises(AggregateNotFoundError):
            repository.get(aggregate1.id, BankAccountWithPydantic)
        event_store.put(aggregate1.collect_events())
        copy = repository.get(aggregate1.id, BankAccountWithPydantic)
        self.assertEqual(copy, aggregate1)

        aggregate2 = BankAccountWithPydantic.open(
            full_name="Phil", email_address="phil@example.com"
        )
        with self.assertRaises(AggregateNotFoundError):
            repository.get(aggregate2.id, BankAccountWithPydantic)
        event_store.put(aggregate2.collect_events())
        copy = repository.get(aggregate2.id, BankAccountWithPydantic)
        self.assertEqual(copy, aggregate2)

        aggregate3 = BankAccountWithPydantic.open(
            full_name="Phil", email_address="phil@example.com"
        )
        with self.assertRaises(AggregateNotFoundError):
            repository.get(aggregate3.id, BankAccountWithPydantic)
        event_store.put(aggregate3.collect_events())
        copy = repository.get(aggregate3.id, BankAccountWithPydantic)
        self.assertEqual(copy, aggregate3)

        assert repository.cache is not None  # for mypy
        self.assertFalse(aggregate1.id in repository.cache.cache)

        reconstructed1 = repository.get(aggregate1.id, BankAccountWithPydantic)
        self.assertEqual(1, reconstructed1.version)
        reconstructed2 = repository.get(aggregate2.id, BankAccountWithPydantic)
        self.assertEqual(1, reconstructed2.version)
        reconstructed3 = repository.get(aggregate3.id, BankAccountWithPydantic)
        self.assertEqual(1, reconstructed3.version)

        aggregate1.append_transaction(Decimal("10.00"))
        event_store.put(aggregate1.collect_events())
        reconstructed4 = repository.get(aggregate1.id, BankAccountWithPydantic)
        self.assertEqual(2, reconstructed4.version)

    def test_cache_fastforward_false(self) -> None:
        transcoder = Transcoder()

        event_recorder = SQLiteAggregateRecorder(SQLiteDatastore(":memory:"))
        event_recorder.create_table()
        event_store = EventStore[Decision](
            mapper=AggregateEventMapper(transcoder=transcoder),
            recorder=event_recorder,
        )
        repository = Repository(
            event_store,
            cache_maxsize=2,
            fastforward=False,
        )

        aggregate = BankAccountWithPydantic.open(
            full_name="Phil", email_address="phil@example.com"
        )
        event_store.put(aggregate.collect_events())
        reconstructed1 = repository.get(aggregate.id, BankAccountWithPydantic)
        self.assertEqual(1, reconstructed1.version)

        aggregate.append_transaction(Decimal("10.00"))
        event_store.put(aggregate.collect_events())
        reconstructed2 = repository.get(aggregate.id, BankAccountWithPydantic)
        self.assertEqual(1, reconstructed2.version)

    def test_cache_raises_aggregate_not_found_when_projector_func_returns_none(
        self,
    ) -> None:
        transcoder = Transcoder()

        event_recorder = SQLiteAggregateRecorder(SQLiteDatastore(":memory:"))
        event_recorder.create_table()
        event_store = EventStore[Decision](
            mapper=AggregateEventMapper(transcoder=transcoder),
            recorder=event_recorder,
        )
        repository = Repository(
            event_store,
            cache_maxsize=2,
        )

        aggregate = BankAccountWithPydantic.open(
            full_name="Phil", email_address="phil@example.com"
        )
        event_store.put(aggregate.collect_events())
        reconstructed = repository.get(aggregate.id, BankAccountWithPydantic)
        self.assertEqual(1, reconstructed.version)

        aggregate.append_transaction(Decimal("10.00"))
        event_store.put(aggregate.collect_events())

        def projector(_: Any, __: Any) -> None:
            return None

        with self.assertRaises(AggregateNotFoundError):
            repository.get(aggregate.id, projector=projector)

    def test_fastforward_lock(self) -> None:
        repository = Repository[Decision](
            EventStore(
                mapper=AggregateEventMapper(transcoder=Transcoder()),
                recorder=POPOAggregateRecorder(),
            ),
            cache_maxsize=2,
        )
        cache_maxsize = repository._fastforward_locks_cache.maxsize
        aggregate_ids = [str(uuid4()) for i in range(cache_maxsize + 1)]
        self.assertEqual(0, len(repository._fastforward_locks_inuse))
        self.assertEqual(0, len(repository._fastforward_locks_cache.cache))

        # Use a lock and check it's "in use".
        repository._use_fastforward_lock(aggregate_ids[0])
        self.assertEqual(1, len(repository._fastforward_locks_inuse))
        self.assertEqual(0, len(repository._fastforward_locks_cache.cache))
        self.assertEqual(1, repository._fastforward_locks_inuse[aggregate_ids[0]][1])

        # Disuse a lock and check it's "cached" and not "in use".
        repository._disuse_fastforward_lock(aggregate_ids[0])
        self.assertEqual(0, len(repository._fastforward_locks_inuse))
        self.assertEqual(1, len(repository._fastforward_locks_cache.cache))

        # Use two locks and check it's "in use" by two users.
        repository._use_fastforward_lock(aggregate_ids[0])
        repository._use_fastforward_lock(aggregate_ids[0])
        self.assertEqual(1, len(repository._fastforward_locks_inuse))
        self.assertEqual(0, len(repository._fastforward_locks_cache.cache))
        self.assertEqual(2, repository._fastforward_locks_inuse[aggregate_ids[0]][1])

        # Disuse the lock and check it's still "in use" by one user.
        repository._disuse_fastforward_lock(aggregate_ids[0])
        self.assertEqual(1, len(repository._fastforward_locks_inuse))
        self.assertEqual(0, len(repository._fastforward_locks_cache.cache))
        self.assertEqual(1, repository._fastforward_locks_inuse[aggregate_ids[0]][1])

        # Disuse the lock and check it's cached and not "in use".
        repository._disuse_fastforward_lock(aggregate_ids[0])
        self.assertEqual(0, len(repository._fastforward_locks_inuse))
        self.assertEqual(1, len(repository._fastforward_locks_cache.cache))

        # Use more locks that the cache holds.
        for aggregate_id in aggregate_ids:
            repository._use_fastforward_lock(aggregate_id)
        self.assertEqual(len(aggregate_ids), len(repository._fastforward_locks_inuse))
        self.assertEqual(0, len(repository._fastforward_locks_cache.cache))

        # Disuse all the locks and check the cache has evicted one.
        self.assertEqual(len(aggregate_ids), cache_maxsize + 1)
        for aggregate_id in aggregate_ids:
            repository._disuse_fastforward_lock(aggregate_id)
        self.assertEqual(0, len(repository._fastforward_locks_inuse))
        self.assertEqual(
            len(aggregate_ids) - 1, len(repository._fastforward_locks_cache.cache)
        )
