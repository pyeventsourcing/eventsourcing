from decimal import Decimal
from functools import reduce
from unittest.case import TestCase
from uuid import uuid4

from eventsourcing.application import (
    AggregateNotFoundError,
    Cache,
    LRUCache,
    Repository,
)
from eventsourcing.domain import Aggregate, Snapshot
from eventsourcing.persistence import (
    DatetimeAsISO,
    DecimalAsStr,
    EventStore,
    JSONTranscoder,
    Mapper,
    UUIDAsHex,
)
from eventsourcing.popo import POPOAggregateRecorder
from eventsourcing.sqlite import SQLiteAggregateRecorder, SQLiteDatastore
from eventsourcing.tests.application import EmailAddressAsStr
from eventsourcing.tests.domain import BankAccount
from eventsourcing.utils import get_topic


class TestRepository(TestCase):
    def test_with_snapshot_store(self) -> None:
        transcoder = JSONTranscoder()
        transcoder.register(UUIDAsHex())
        transcoder.register(DecimalAsStr())
        transcoder.register(DatetimeAsISO())
        transcoder.register(EmailAddressAsStr())

        event_recorder = SQLiteAggregateRecorder(SQLiteDatastore(":memory:"))
        event_recorder.create_table()
        event_store = EventStore(
            mapper=Mapper(transcoder=transcoder),
            recorder=event_recorder,
        )
        snapshot_recorder = SQLiteAggregateRecorder(SQLiteDatastore(":memory:"))
        snapshot_recorder.create_table()
        snapshot_store = EventStore(
            mapper=Mapper(transcoder=transcoder),
            recorder=snapshot_recorder,
        )
        repository = Repository(event_store, snapshot_store=snapshot_store)

        # Check key error.
        with self.assertRaises(AggregateNotFoundError):
            repository.get(uuid4())

        # Open an account.
        account = BankAccount.open(
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

        copy = repository.get(account.id)
        assert isinstance(copy, BankAccount)
        # Check copy has correct attribute values.
        assert copy.id == account.id
        assert copy.balance == Decimal("65.00")

        snapshot = Snapshot(
            originator_id=account.id,
            originator_version=account.version,
            timestamp=Snapshot.create_timestamp(),
            topic=get_topic(type(account)),
            state=account.__dict__,
        )
        snapshot_store.put([snapshot])

        copy2 = repository.get(account.id)
        assert isinstance(copy2, BankAccount)

        # Check copy has correct attribute values.
        assert copy2.id == account.id
        assert copy2.balance == Decimal("65.00")

        # Credit the account.
        account.append_transaction(Decimal("10.00"))
        event_store.put(account.collect_events())

        # Check copy has correct attribute values.
        copy3 = repository.get(account.id)
        assert isinstance(copy3, BankAccount)

        assert copy3.id == account.id
        assert copy3.balance == Decimal("75.00")

        # Check can get old version of account.
        copy4 = repository.get(account.id, version=copy.version)
        assert isinstance(copy4, BankAccount)
        assert copy4.balance == Decimal("65.00")

        copy5 = repository.get(account.id, version=1)
        assert isinstance(copy5, BankAccount)
        assert copy5.balance == Decimal("0.00")

        copy6 = repository.get(account.id, version=2)
        assert isinstance(copy6, BankAccount)
        assert copy6.balance == Decimal("10.00")

        copy7 = repository.get(account.id, version=3)
        assert isinstance(copy7, BankAccount)
        assert copy7.balance == Decimal("35.00"), copy7.balance

        copy8 = repository.get(account.id, version=4)
        assert isinstance(copy8, BankAccount)
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
        transcoder = JSONTranscoder()
        transcoder.register(UUIDAsHex())
        transcoder.register(DecimalAsStr())
        transcoder.register(DatetimeAsISO())
        transcoder.register(EmailAddressAsStr())

        event_recorder = SQLiteAggregateRecorder(SQLiteDatastore(":memory:"))
        event_recorder.create_table()
        event_store = EventStore(
            mapper=Mapper(transcoder=transcoder),
            recorder=event_recorder,
        )
        repository = Repository(event_store)

        # Check key error.
        with self.assertRaises(AggregateNotFoundError):
            repository.get(uuid4())

        # Open an account.
        account = BankAccount.open(
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

        copy = repository.get(account.id)
        assert isinstance(copy, BankAccount)
        # Check copy has correct attribute values.
        assert copy.id == account.id
        assert copy.balance == Decimal("65.00")

        # Credit the account.
        account.append_transaction(Decimal("10.00"))
        event_store.put(account.collect_events())

        # Check copy has correct attribute values.
        copy2 = repository.get(account.id)
        assert isinstance(copy2, BankAccount)

        assert copy2.id == account.id
        assert copy2.balance == Decimal("75.00")

        # Check can get old version of account.
        copy3 = repository.get(account.id, version=copy.version)
        assert isinstance(copy3, BankAccount)
        assert copy3.balance == Decimal("65.00")

        copy4 = repository.get(account.id, version=1)
        assert isinstance(copy4, BankAccount)
        assert copy4.balance == Decimal("0.00")

        copy5 = repository.get(account.id, version=2)
        assert isinstance(copy5, BankAccount)
        assert copy5.balance == Decimal("10.00")

        copy6 = repository.get(account.id, version=3)
        assert isinstance(copy6, BankAccount)
        assert copy6.balance == Decimal("35.00"), copy6.balance

        copy7 = repository.get(account.id, version=4)
        assert isinstance(copy7, BankAccount)
        assert copy7.balance == Decimal("65.00"), copy7.balance

    def test_with_alternative_mutator_function(self):
        def mutator(initial, domain_events):
            return reduce(lambda a, e: e.mutate(a), domain_events, initial)

        transcoder = JSONTranscoder()
        transcoder.register(UUIDAsHex())
        transcoder.register(DecimalAsStr())
        transcoder.register(DatetimeAsISO())
        transcoder.register(EmailAddressAsStr())

        event_recorder = SQLiteAggregateRecorder(SQLiteDatastore(":memory:"))
        event_recorder.create_table()
        event_store = EventStore(
            mapper=Mapper(transcoder=transcoder),
            recorder=event_recorder,
        )
        snapshot_recorder = SQLiteAggregateRecorder(SQLiteDatastore(":memory:"))
        snapshot_recorder.create_table()
        snapshot_store = EventStore(
            mapper=Mapper(transcoder=transcoder),
            recorder=snapshot_recorder,
        )
        repository = Repository(event_store, snapshot_store=snapshot_store)

        # Check key error.
        with self.assertRaises(AggregateNotFoundError):
            repository.get(uuid4())

        # Open an account.
        account = BankAccount.open(
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

        copy = repository.get(account.id, projector_func=mutator)
        assert isinstance(copy, BankAccount)
        # Check copy has correct attribute values.
        assert copy.id == account.id
        assert copy.balance == Decimal("65.00")

        snapshot = Snapshot(
            originator_id=account.id,
            originator_version=account.version,
            timestamp=Snapshot.create_timestamp(),
            topic=get_topic(type(account)),
            state=account.__dict__,
        )
        snapshot_store.put([snapshot])

        copy2 = repository.get(account.id)
        assert isinstance(copy2, BankAccount)

        # Check copy has correct attribute values.
        assert copy2.id == account.id
        assert copy2.balance == Decimal("65.00")

        # Credit the account.
        account.append_transaction(Decimal("10.00"))
        event_store.put(account.collect_events())

        # Check copy has correct attribute values.
        copy3 = repository.get(account.id)
        assert isinstance(copy3, BankAccount)

        assert copy3.id == account.id
        assert copy3.balance == Decimal("75.00")

        # Check can get old version of account.
        copy4 = repository.get(account.id, version=copy.version)
        assert isinstance(copy4, BankAccount)
        assert copy4.balance == Decimal("65.00")

        copy5 = repository.get(account.id, version=1)
        assert isinstance(copy5, BankAccount)
        assert copy5.balance == Decimal("0.00")

        copy6 = repository.get(account.id, version=2)
        assert isinstance(copy6, BankAccount)
        assert copy6.balance == Decimal("10.00")

        copy7 = repository.get(account.id, version=3)
        assert isinstance(copy7, BankAccount)
        assert copy7.balance == Decimal("35.00"), copy7.balance

        copy8 = repository.get(account.id, version=4)
        assert isinstance(copy8, BankAccount)
        assert copy8.balance == Decimal("65.00"), copy8.balance

    def test_contains(self):
        transcoder = JSONTranscoder()
        transcoder.register(UUIDAsHex())
        transcoder.register(DecimalAsStr())
        transcoder.register(DatetimeAsISO())

        event_recorder = POPOAggregateRecorder()
        event_store = EventStore(
            mapper=Mapper(transcoder=transcoder),
            recorder=event_recorder,
        )

        aggregate = Aggregate()
        event_store.put(aggregate.collect_events())

        repository = Repository(event_store)
        self.assertTrue(aggregate.id in repository)
        self.assertFalse(uuid4() in repository)

    def test_cache_maxsize_zero(self):
        transcoder = JSONTranscoder()
        transcoder.register(UUIDAsHex())
        transcoder.register(DecimalAsStr())
        transcoder.register(DatetimeAsISO())
        transcoder.register(EmailAddressAsStr())

        event_recorder = SQLiteAggregateRecorder(SQLiteDatastore(":memory:"))
        event_recorder.create_table()
        event_store = EventStore(
            mapper=Mapper(transcoder=transcoder),
            recorder=event_recorder,
        )
        repository = Repository(event_store, cache_maxsize=0)
        self.assertEqual(type(repository.cache), Cache)

        aggregate = Aggregate()

        self.assertFalse(aggregate.id in repository)
        event_store.put(aggregate.collect_events())
        self.assertTrue(aggregate.id in repository)

        self.assertEqual(1, repository.get(aggregate.id).version)

        aggregate.trigger_event(Aggregate.Event)
        event_store.put(aggregate.collect_events())
        self.assertEqual(2, repository.get(aggregate.id).version)

    def test_cache_maxsize_nonzero(self):
        transcoder = JSONTranscoder()
        transcoder.register(UUIDAsHex())
        transcoder.register(DecimalAsStr())
        transcoder.register(DatetimeAsISO())
        transcoder.register(EmailAddressAsStr())

        event_recorder = SQLiteAggregateRecorder(SQLiteDatastore(":memory:"))
        event_recorder.create_table()
        event_store = EventStore(
            mapper=Mapper(transcoder=transcoder),
            recorder=event_recorder,
        )
        repository = Repository(event_store, cache_maxsize=2)
        self.assertEqual(type(repository.cache), LRUCache)

        aggregate1 = Aggregate()
        self.assertFalse(aggregate1.id in repository)
        event_store.put(aggregate1.collect_events())
        self.assertTrue(aggregate1.id in repository)

        aggregate2 = Aggregate()
        self.assertFalse(aggregate2.id in repository)
        event_store.put(aggregate2.collect_events())
        self.assertTrue(aggregate2.id in repository)

        aggregate3 = Aggregate()
        self.assertFalse(aggregate3.id in repository)
        event_store.put(aggregate3.collect_events())
        self.assertTrue(aggregate3.id in repository)

        self.assertFalse(aggregate1.id in repository.cache.cache)

        self.assertEqual(1, repository.get(aggregate1.id).version)
        self.assertEqual(1, repository.get(aggregate2.id).version)
        self.assertEqual(1, repository.get(aggregate3.id).version)

        aggregate1.trigger_event(Aggregate.Event)
        event_store.put(aggregate1.collect_events())
        self.assertEqual(2, repository.get(aggregate1.id).version)

    def test_cache_fastforward_false(self):
        transcoder = JSONTranscoder()
        transcoder.register(UUIDAsHex())
        transcoder.register(DecimalAsStr())
        transcoder.register(DatetimeAsISO())
        transcoder.register(EmailAddressAsStr())

        event_recorder = SQLiteAggregateRecorder(SQLiteDatastore(":memory:"))
        event_recorder.create_table()
        event_store = EventStore(
            mapper=Mapper(transcoder=transcoder),
            recorder=event_recorder,
        )
        repository = Repository(
            event_store,
            cache_maxsize=2,
            fastforward=False,
        )

        aggregate = Aggregate()
        event_store.put(aggregate.collect_events())
        self.assertEqual(1, repository.get(aggregate.id).version)

        aggregate.trigger_event(Aggregate.Event)
        event_store.put(aggregate.collect_events())
        self.assertEqual(1, repository.get(aggregate.id).version)

    def test_cache_raises_aggregate_not_found_when_projector_func_returns_none(self):
        transcoder = JSONTranscoder()
        transcoder.register(UUIDAsHex())
        transcoder.register(DecimalAsStr())
        transcoder.register(DatetimeAsISO())
        transcoder.register(EmailAddressAsStr())

        event_recorder = SQLiteAggregateRecorder(SQLiteDatastore(":memory:"))
        event_recorder.create_table()
        event_store = EventStore(
            mapper=Mapper(transcoder=transcoder),
            recorder=event_recorder,
        )
        repository = Repository(
            event_store,
            cache_maxsize=2,
        )

        aggregate = Aggregate()
        event_store.put(aggregate.collect_events())
        self.assertEqual(1, repository.get(aggregate.id).version)

        aggregate.trigger_event(Aggregate.Event)
        event_store.put(aggregate.collect_events())
        with self.assertRaises(AggregateNotFoundError):
            repository.get(aggregate.id, projector_func=lambda _, __: None)

    def test_fastforward_lock(self):
        repository = Repository(
            EventStore(
                mapper=Mapper(transcoder=JSONTranscoder()),
                recorder=POPOAggregateRecorder(),
            ),
            cache_maxsize=2,
        )
        cache_maxsize = repository._fastforward_locks_cache.maxsize
        aggregate_ids = [uuid4() for i in range(cache_maxsize + 1)]
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
