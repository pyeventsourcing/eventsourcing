from math import ceil, log
from unittest.case import skip

from eventsourcing.domain.model.sequence import CompoundSequence, Sequence
from eventsourcing.tests.sequenced_item_tests.test_cassandra_active_record_strategy import \
    WithCassandraActiveRecordStrategies

try:
    from queue import Queue
except ImportError:
    from Queue import Queue
from threading import Thread
from uuid import uuid4, UUID

from eventsourcing.exceptions import CompoundSequenceFullError, SequenceFullError
from eventsourcing.infrastructure.event_sourced_repos.sequence import CompoundSequenceRepository, SequenceRepository
from eventsourcing.tests.base import notquick
from eventsourcing.tests.sequenced_item_tests.base import WithPersistencePolicies
from eventsourcing.tests.sequenced_item_tests.test_sqlalchemy_active_record_strategy import \
    WithSQLAlchemyActiveRecordStrategies


class TestSequenceWithSQLAlchemy(WithSQLAlchemyActiveRecordStrategies, WithPersistencePolicies):
    # use_named_temporary_file = True

    def setUp(self):
        super(TestSequenceWithSQLAlchemy, self).setUp()
        self.repo = SequenceRepository(self.entity_event_store, sequence_size=3)

    def test_simple_sequence(self):

        # Start a new sequence.
        sequence_id = uuid4()

        # Check get_reader() can create a new sequence.

        sequence = self.repo[sequence_id]
        self.assertIsInstance(sequence, Sequence)
        self.assertIsNone(sequence.meta)

        sequence.register()

        self.assertEqual(sequence.id, sequence_id)

        # Append some items.
        sequence.append('item1', sequence.get_position())
        sequence.append('item2', sequence.get_position())
        sequence.append('item3', sequence.get_position())

        # Check the sequence in the self.repo.
        sequence = self.repo[sequence_id]
        self.assertIsNotNone(sequence.meta)
        # self.assertEqual(sequence.meta.max_size, self.repo.sequence_size)

        # Check the sequence indexing.
        self.assertEqual(sequence[0], 'item1')
        self.assertEqual(sequence[-3], 'item1')
        self.assertEqual(sequence[1], 'item2')
        self.assertEqual(sequence[-2], 'item2')
        self.assertEqual(sequence[2], 'item3')
        self.assertEqual(sequence[-1], 'item3')

        # Check slices also work.
        self.assertEqual(sequence[0:3], ['item1', 'item2', 'item3'])
        self.assertEqual(sequence[0:2], ['item1', 'item2'])
        self.assertEqual(sequence[0:-1], ['item1', 'item2'])
        self.assertEqual(sequence[0:1], ['item1'])
        self.assertEqual(sequence[0:-2], ['item1'])
        self.assertEqual(sequence[1:3], ['item2', 'item3'])
        self.assertEqual(sequence[1:2], ['item2'])
        self.assertEqual(sequence[-2:-1], ['item2'])
        self.assertEqual(sequence[1:1], [])
        self.assertEqual(sequence[-2:-2], [])
        self.assertEqual(sequence[2:3], ['item3'])
        self.assertEqual(sequence[3:3], [])
        self.assertEqual(sequence[0:300], ['item1', 'item2', 'item3'])
        self.assertEqual(sequence[2:1], [])
        self.assertEqual(sequence[2:-2], [])

        self.assertEqual(sequence[0:], ['item1', 'item2', 'item3'])
        self.assertEqual(sequence[1:], ['item2', 'item3'])
        self.assertEqual(sequence[2:], ['item3'])
        self.assertEqual(sequence[3:], [])
        self.assertEqual(sequence[4:], [])
        self.assertEqual(sequence[-1:], ['item3'])
        self.assertEqual(sequence[-2:], ['item2', 'item3'])
        self.assertEqual(sequence[-3:], ['item1', 'item2', 'item3'])
        self.assertEqual(sequence[-4:], ['item1', 'item2', 'item3'])

        self.assertEqual(sequence[:0], [])
        self.assertEqual(sequence[:1], ['item1'])
        self.assertEqual(sequence[:2], ['item1', 'item2'])
        self.assertEqual(sequence[:3], ['item1', 'item2', 'item3'])
        self.assertEqual(sequence[:4], ['item1', 'item2', 'item3'])
        self.assertEqual(sequence[:-1], ['item1', 'item2'])
        self.assertEqual(sequence[:-2], ['item1'])
        self.assertEqual(sequence[:-3], [])
        self.assertEqual(sequence[:-4], [])

        self.assertEqual(sequence[:], ['item1', 'item2', 'item3'])

        # Check iterator.
        for i, item in enumerate(sequence):
            self.assertEqual(item, 'item{}'.format(i + 1))

        # Check len.
        self.assertEqual(len(sequence), 3)

        # Check full error.
        with self.assertRaises(SequenceFullError):
            # Fail to append fourth item (sequence size is 3).
            sequence.append('item1', sequence.get_position())

        # Check index errors.
        with self.assertRaises(IndexError):
            # noinspection PyStatementEffect
            sequence[3]

        with self.assertRaises(IndexError):
            # noinspection PyStatementEffect
            sequence[-4]


class TestCompoundSequenceWithSQLAlchemy(WithSQLAlchemyActiveRecordStrategies, WithPersistencePolicies):
    use_named_temporary_file = True

    def setUp(self):
        super(TestCompoundSequenceWithSQLAlchemy, self).setUp()
        self.repo = CompoundSequenceRepository(
            event_store=self.entity_event_store,
        )
        self.subrepo = self.repo.subrepo
        self.result_queue = None

    def test_compound_sequence_short(self):
        # Can add zero items if max_size is zero.
        root, added = self.start_and_append(0, 0)
        # Check we got a compound sequence.
        self.assertIsInstance(root, CompoundSequence)
        # Check none was added.
        self.assertEqual(added, [])

        # Can add 1 items if max_size is 1.
        root, added = self.start_and_append(sequence_size=1, num_items=1)

        # Check we got a compound sequence.
        self.assertIsInstance(root, CompoundSequence)
        assert isinstance(root, CompoundSequence)
        # Check something was added.
        self.assertTrue(added)

        # Check root has an ID.
        self.assertTrue(root.id)
        # Get the root sequence.
        root_sequence = self.subrepo[root.id]
        # Check it has some meta data.
        self.assertTrue(root_sequence.meta)
        # Check the root sequence has length 1.
        self.assertEqual(len(root_sequence), 1)
        # Check the root sequence is full.
        with self.assertRaises(SequenceFullError):
            root_sequence.append(1, root_sequence.get_position())

        # Get the current apex ID from the root sequence.
        apex_id = root_sequence[-1]
        # Check it's a UUID.
        self.assertIsInstance(apex_id, UUID)
        # Get the apex sequence.
        apex_sequence = self.subrepo[apex_id]
        self.assertTrue(apex_sequence.meta)
        # Check the apex sequence has length 1.
        self.assertEqual(len(apex_sequence), 1)
        # Check the apex sequence is full.
        with self.assertRaises(SequenceFullError):
            apex_sequence.append(1, apex_sequence.get_position())

        # Get the item.
        item1 = apex_sequence[-1]
        # Check it's a UUID.
        self.assertIsInstance(apex_id, UUID)
        # Check it's the last things that was added above.
        self.assertEqual(item1, added[-1])

        # Check the "last sequence" is the apex we got above.
        _, _, _, last_sequence, i = root.get_last_sequence()
        self.assertEqual(last_sequence, apex_sequence)
        # Check the 'i' value of the apex is 0.
        self.assertEqual(i, 0)

        # Check the "last item" is the item we got above.
        last_item, n = root.get_last_item_and_n()
        self.assertEqual(last_item, added[-1])
        # Check the index of the item.
        self.assertEqual(n, 0)

        # Can add 2 items if max_size is 2.
        root, added = self.start_and_append(sequence_size=2, num_items=2)
        last_item, n = root.get_last_item_and_n()
        self.assertEqual(last_item, added[-1])
        self.assertEqual(n, 1)
        self.assertEqual(len(root), 2)
        self.assertEqual(len(self.subrepo[root.id]), 1)

        # Can add 3 items if max_size is 2.
        root, added = self.start_and_append(sequence_size=2, num_items=3)
        last_item, n = root.get_last_item_and_n()
        self.assertEqual(last_item, added[-1])
        self.assertEqual(n, 2)
        self.assertEqual(len(root), 3)
        self.assertEqual(len(self.subrepo[root.id]), 2)

        # self.assertEqual(len(self.subrepo[root[0]]), 2)
        # _, _, _, last_sequence, i = root.get_last_sequence()
        # self.assertEqual(last_sequence.id, self.subrepo[root[-1]][-1])
        self.assertEqual(len(last_sequence), 1)
        # self.assertEqual(len(self.subrepo[self.subrepo[root[1]][1]]), 1)

        # Check can append another, that it's not full.
        last_sequence.append(1, last_sequence.get_position())

        # Can add 4 items if max_size is 2.
        root, added = self.start_and_append(sequence_size=2, num_items=4)
        last_item, n = root.get_last_item_and_n()
        self.assertEqual(last_item, added[-1])
        self.assertEqual(n, 3)

        # Can add 6 items if max_size is 3.
        root, added = self.start_and_append(sequence_size=3, num_items=7)
        last_item, n = root.get_last_item_and_n()
        self.assertEqual(last_item, added[-1])
        self.assertEqual(n, 6)

        root, added = self.start_and_append(sequence_size=3, num_items=9)
        last_item, n = root.get_last_item_and_n()
        self.assertEqual(last_item, added[-1])
        self.assertEqual(n, 8)

        root, added = self.start_and_append(sequence_size=3, num_items=10)
        last_item, n = root.get_last_item_and_n()
        self.assertEqual(last_item, added[-1])
        self.assertEqual(n, 9)

        root, added = self.start_and_append(sequence_size=4, num_items=16)
        last_item, n = root.get_last_item_and_n()
        self.assertEqual(last_item, added[-1])
        self.assertEqual(n, 15)

        root, added = self.start_and_append(sequence_size=4, num_items=27)
        last_item, n = root.get_last_item_and_n()
        self.assertEqual(last_item, added[-1])
        self.assertEqual(n, 26)

        # Can't add 2 items if max_size is 1.
        with self.assertRaises(CompoundSequenceFullError):
            self.start_and_append(sequence_size=1, num_items=2)

        # Can't add 5 items if max_size is 2.
        with self.assertRaises(CompoundSequenceFullError):
            self.start_and_append(sequence_size=2, num_items=5)

        # Can't add 28 items if max_size is 3.
        with self.assertRaises(CompoundSequenceFullError):
            self.start_and_append(sequence_size=3, num_items=28)

    def test_compound_sequence_threads_1_1_1(self):
        self._test_compound_sequence_threads(1, 1, 1)

    def test_compound_sequence_threads_2_2_2(self):
        self._test_compound_sequence_threads(2, 2, 2)

    def test_compound_sequence_threads_3_3_9(self):
        self._test_compound_sequence_threads(3, 3, 9)

    def test_compound_sequence_threads_3_9_3(self):
        self._test_compound_sequence_threads(3, 9, 3)

    @notquick
    def test_compound_sequence_threads_4_4_64(self):
        self._test_compound_sequence_threads(4, 4, 64)

    @notquick
    def test_compound_sequence_threads_4_8_32(self):
        self._test_compound_sequence_threads(4, 8, 32)

    @notquick
    def test_compound_sequence_threads_4_16_16(self):
        self._test_compound_sequence_threads(4, 16, 16)

    @notquick
    def test_compound_sequence_threads_4_32_8(self):
        self._test_compound_sequence_threads(4, 32, 8)

    @skip("Avoid 'database is locked' error from SQLite")
    @notquick
    def test_compound_sequence_threads_4_64_4(self):
        self._test_compound_sequence_threads(4, 64, 4)

    @skip("Avoid 'database is locked' error from SQLite")
    @notquick
    def test_compound_sequence_threads_4_256_1(self):
        self._test_compound_sequence_threads(4, 256, 1)

    def _test_compound_sequence_threads(self, sequence_size, num_threads, num_items_per_thread):
        error_queue = Queue()
        full_queue = Queue()
        self.result_queue = Queue()
        assert num_threads * num_items_per_thread == sequence_size ** sequence_size, (
            num_threads * num_items_per_thread, sequence_size ** sequence_size)
        root = self.start_root(sequence_size=sequence_size)

        def task():
            try:
                for item in self.append_items(num_items_per_thread, root):
                    self.result_queue.put(item)
            except CompoundSequenceFullError as e:
                full_queue.put(e)
            except Exception as e:
                error_queue.put(e)

        # Have many threads each trying to fill up the log
        threads = [Thread(target=task) for _ in range(num_threads)]
        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Gather thread exception.
        errors = []
        while not error_queue.empty():
            errors.append(error_queue.get())

        # Gather thread exception.
        fulls = []
        while not full_queue.empty():
            fulls.append(full_queue.get())

        results = []
        while not self.result_queue.empty():
            results.append(self.result_queue.get())

        # Check there are no thread exceptions.
        if errors:
            raise errors[0]
        self.assertFalse(errors)

        if fulls:
            raise fulls[0]
        self.assertFalse(fulls)

        expected_results = min(sequence_size ** sequence_size, num_threads * num_items_per_thread)
        self.assertEqual(len(results), expected_results)

        # Check the height of the root.
        # - limited either by the max capacity
        #   or by the number of added item

        if expected_results <= 1:
            expected_height = expected_results
        else:
            expected_height = ceil(log(expected_results, sequence_size))

        self.assertEqual(len(self.subrepo[root.id]), expected_height)

    def start_and_append(self, sequence_size, num_items):
        root = self.start_root(sequence_size)
        items = self.append_items(num_items, root)

        return root, list(items)

    def append_items(self, num_items, root):
        for i in range(num_items):
            # item = uuid4()
            item = 'item-{}'.format(i)
            root.append(item)
            yield item

    def start_root(self, sequence_size):
        self.repo.sequence_size = sequence_size
        self.repo.subrepo.sequence_size = sequence_size
        root = self.repo[uuid4()]
        return root

    @notquick
    def test_compound_sequence_long(self):
        # Can add 256 items if max_size is 4.
        self.start_and_append(sequence_size=4, num_items=256)

        # Can't add 257 items if max_size is 4.
        with self.assertRaises(CompoundSequenceFullError):
            self.start_and_append(sequence_size=4, num_items=257)

        # Can add 100 items if max_size is 10000.
        #  - Should have capacity for 10000**10000 items,
        #    which is 1e+40000 items, but is not checked here.
        root, added = self.start_and_append(sequence_size=10000, num_items=100)
        self.assertEqual(root.get_last_item_and_n(), (added[-1], 99))
        self.assertEqual(len(root), 100)
        # Check depth is 1.
        self.assertEqual(len(self.subrepo[root.id]), 1)

        # Can add 101 items if max_size is 100.
        root, added = self.start_and_append(sequence_size=100, num_items=101)
        self.assertEqual(root.get_last_item_and_n(), (added[-1], 100))
        self.assertEqual(len(root), 101)
        # Check depth is 2.
        self.assertEqual(len(self.subrepo[root.id]), 2)

    def test_iterator_2_3(self):
        self._test_iterator(sequence_size=2, num_items=3)

    def test_iterator_2_4(self):
        self._test_iterator(sequence_size=2, num_items=3)

    def test_iterator_3_20(self):
        self._test_iterator(sequence_size=3, num_items=20)

    def test_iterator_3_27(self):
        self._test_iterator(sequence_size=3, num_items=27)

    @notquick
    def test_iterator_4_230(self):
        self._test_iterator(sequence_size=4, num_items=230)

    def test_iterator_1000_23(self):
        self._test_iterator(sequence_size=1000, num_items=23)

    def _test_iterator(self, sequence_size, num_items):
        sequence, added = self.start_and_append(sequence_size, num_items)

        self.assertEqual(sequence[0], added[0])
        self.assertEqual(sequence[-3], added[-3])
        self.assertEqual(sequence[1], added[1])
        self.assertEqual(sequence[-2], added[-2])
        self.assertEqual(sequence[2], added[2])
        self.assertEqual(sequence[-1], added[-1])

        # Check slices also work.
        self.assertEqual(list(sequence[0:3]), added[0:3])
        self.assertEqual(list(sequence[0:2]), added[0:2])
        self.assertEqual(list(sequence[0:-1]), added[0:-1])
        self.assertEqual(list(sequence[0:1]), added[0:1])
        self.assertEqual(list(sequence[0:-2]), added[0:-2])
        self.assertEqual(list(sequence[1:3]), added[1:3])
        self.assertEqual(list(sequence[1:2]), added[1:2])
        self.assertEqual(list(sequence[-2:-1]), added[-2:-1])
        self.assertEqual(list(sequence[1:1]), added[1:1])
        self.assertEqual(list(sequence[-2:-2]), added[-2:-2])
        self.assertEqual(list(sequence[2:3]), added[2:3])
        self.assertEqual(list(sequence[3:3]), added[3:3])
        self.assertEqual(list(sequence[0:300]), added[0:300])
        self.assertEqual(list(sequence[2:1]), added[2:1])
        self.assertEqual(list(sequence[2:-2]), added[2:-2])

        self.assertEqual(list(sequence[0:]), added[0:])
        self.assertEqual(list(sequence[1:]), added[1:])
        self.assertEqual(list(sequence[2:]), added[2:])
        self.assertEqual(list(sequence[3:]), added[3:])
        self.assertEqual(list(sequence[4:]), added[4:])
        self.assertEqual(list(sequence[-1:]), added[-1:])
        self.assertEqual(list(sequence[-2:]), added[-2:])
        self.assertEqual(list(sequence[-3:]), added[-3:])
        self.assertEqual(list(sequence[-4:]), added[-4:])

        self.assertEqual(list(sequence[:0]), added[:0])
        self.assertEqual(list(sequence[:1]), added[:1])
        self.assertEqual(list(sequence[:2]), added[:2])
        self.assertEqual(list(sequence[:3]), added[:3])
        self.assertEqual(list(sequence[:4]), added[:4])
        self.assertEqual(list(sequence[:-1]), added[:-1])
        self.assertEqual(list(sequence[:-2]), added[:-2])
        self.assertEqual(list(sequence[:-3]), added[:-3])
        self.assertEqual(list(sequence[:-4]), added[:-4])

        # Check iterator.
        for i, item in enumerate(sequence):
            self.assertEqual(item, 'item-{}'.format(i))

        # Check len.
        self.assertEqual(len(sequence), num_items)

        # Check index errors.
        # - out of range
        with self.assertRaises(IndexError):
            # noinspection PyStatementEffect
            sequence[num_items]

        with self.assertRaises(IndexError):
            # noinspection PyStatementEffect
            sequence[- num_items - 1]

        return sequence, added


class TestSequenceWithCassandra(WithCassandraActiveRecordStrategies, TestSequenceWithSQLAlchemy):
    pass


class TestCompoundSequenceWithCassandra(WithCassandraActiveRecordStrategies, TestCompoundSequenceWithSQLAlchemy):
    pass
