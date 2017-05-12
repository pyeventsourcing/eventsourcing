from math import ceil, log
from random import shuffle
from sys import version_info
from threading import Thread
from unittest.case import skip, skipIf
from uuid import UUID, uuid4

from eventsourcing.domain.model.array import AbstractArrayRepository, Array, BigArray
from eventsourcing.exceptions import ArrayIndexError, ConcurrencyError
from eventsourcing.infrastructure.event_sourced_repos.array import ArrayRepository, BigArrayRepository
from eventsourcing.tests.base import notquick
from eventsourcing.tests.sequenced_item_tests.base import WithPersistencePolicies
from eventsourcing.tests.sequenced_item_tests.test_cassandra_active_record_strategy import \
    WithCassandraActiveRecordStrategies
from eventsourcing.tests.sequenced_item_tests.test_sqlalchemy_active_record_strategy import \
    WithSQLAlchemyActiveRecordStrategies

try:
    from unittest import mock
except:
    import mock

try:
    from queue import Queue
except ImportError:
    from Queue import Queue


class TestArrayWithSQLAlchemy(WithSQLAlchemyActiveRecordStrategies, WithPersistencePolicies):
    def setUp(self):
        super(TestArrayWithSQLAlchemy, self).setUp()
        self.repo = ArrayRepository(
            array_size=3,
            event_store=self.entity_event_store,
        )

    def test_array(self):

        # Start a new array.
        array_id = uuid4()
        array = self.repo[array_id]
        self.assertIsInstance(array, Array)
        self.assertEqual(array.id, array_id)

        # Add some items.
        array[0] = 'item1'
        array.append('item2')
        array.append('item3')

        # Check the array in the self.repo.
        array = self.repo[array_id]

        # Check the array indexing.
        self.assertEqual(array[0], 'item1')
        self.assertEqual(array[-3], 'item1')
        self.assertEqual(array[1], 'item2')
        self.assertEqual(array[-2], 'item2')
        self.assertEqual(array[2], 'item3')
        self.assertEqual(array[-1], 'item3')

        # Check slices also work.
        self.assertEqual(array[0:3], ['item1', 'item2', 'item3'])
        self.assertEqual(array[0:2], ['item1', 'item2'])
        self.assertEqual(array[0:-1], ['item1', 'item2'])
        self.assertEqual(array[0:1], ['item1'])
        self.assertEqual(array[0:-2], ['item1'])
        self.assertEqual(array[1:3], ['item2', 'item3'])
        self.assertEqual(array[1:2], ['item2'])
        self.assertEqual(array[-2:-1], ['item2'])
        self.assertEqual(array[1:1], [])
        self.assertEqual(array[-2:-2], [])
        self.assertEqual(array[2:3], ['item3'])
        self.assertEqual(array[3:3], [])
        self.assertEqual(array[0:300], ['item1', 'item2', 'item3'])
        self.assertEqual(array[2:1], [])
        self.assertEqual(array[2:-2], [])

        self.assertEqual(array[0:], ['item1', 'item2', 'item3'])
        self.assertEqual(array[1:], ['item2', 'item3'])
        self.assertEqual(array[2:], ['item3'])
        self.assertEqual(array[3:], [])
        self.assertEqual(array[4:], [])
        self.assertEqual(array[-1:], ['item3'])
        self.assertEqual(array[-2:], ['item2', 'item3'])
        self.assertEqual(array[-3:], ['item1', 'item2', 'item3'])
        self.assertEqual(array[-4:], ['item1', 'item2', 'item3'])

        self.assertEqual(array[:0], [])
        self.assertEqual(array[:1], ['item1'])
        self.assertEqual(array[:2], ['item1', 'item2'])
        self.assertEqual(array[:3], ['item1', 'item2', 'item3'])
        self.assertEqual(array[:4], ['item1', 'item2', 'item3'])
        self.assertEqual(array[:-1], ['item1', 'item2'])
        self.assertEqual(array[:-2], ['item1'])
        self.assertEqual(array[:-3], [])
        self.assertEqual(array[:-4], [])

        self.assertEqual(array[:], ['item1', 'item2', 'item3'])

        # Check iterator.
        for i, item in enumerate(array):
            self.assertEqual(item, 'item{}'.format(i + 1))

        # Check len.
        self.assertEqual(len(array), 3)

        # Check full error.
        with self.assertRaises(ArrayIndexError):
            # Fail to append fourth item (array size is 3).
            array.append('item1')

        # Check index errors.
        with self.assertRaises(ArrayIndexError):
            # noinspection PyStatementEffect
            array[3]

        with self.assertRaises(ArrayIndexError):
            # noinspection PyStatementEffect
            array[-4]


class BigArrayTestCase(WithSQLAlchemyActiveRecordStrategies, WithPersistencePolicies):
    def start_and_append(self, array_size, num_items):
        array = self.get_big_array(array_size)
        items = self.append_items(num_items, array)
        return array, list(items)

    def append_items(self, num_items, array):
        for i in range(num_items):
            item = 'item-{}'.format(i)
            array.append(item)
            yield item

    def start_and_set(self, base_size, num_items, offset=0):
        array = self.get_big_array(base_size)
        items = self.set_items(num_items, array, offset)
        return array, list(items)

    def set_items(self, num_items, array, offset):
        for i in range(offset, offset + num_items):
            item = 'item-{}'.format(i)
            array[i] = item
            yield item

    def get_big_array(self, base_size):
        self.repo.subrepo.array_size = base_size
        root = self.repo[uuid4()]
        return root


class TestBigArrayWithSQLAlchemy(BigArrayTestCase):
    def setUp(self):
        super(TestBigArrayWithSQLAlchemy, self).setUp()
        self.repo = BigArrayRepository(
            base_size=None,
            event_store=self.entity_event_store,
        )
        self.subrepo = self.repo.subrepo
        self.result_queue = None

    def test_big_array_short(self):
        # Can add zero items if base_size is zero.
        root, added = self.start_and_set(0, 0)
        # Check we got a compound array.
        self.assertIsInstance(root, BigArray)
        # Check none was added.
        self.assertEqual(added, [])

        # Can add 1 items if base_size is 1.
        root, added = self.start_and_set(base_size=1, num_items=1)

        # Check we got a compound array.
        self.assertIsInstance(root, BigArray)
        assert isinstance(root, BigArray)
        # Check something was added.
        self.assertTrue(added)

        # Check root has an ID.
        self.assertTrue(root.id)
        # Get the root array.
        root_array = self.subrepo[root.id]
        # Check the root array has length 1.
        self.assertEqual(len(root_array), 1)
        # Check the root array is full.
        with self.assertRaises(ArrayIndexError):
            root_array.append(1)

        # Get the current apex ID from the root array.
        apex_id = root_array[-1]
        # Check it's a UUID.
        self.assertIsInstance(apex_id, UUID)
        # Get the apex array.
        apex_array = self.subrepo[apex_id]
        # Check the apex array has length 1.
        self.assertEqual(len(apex_array), 1)
        # Check the apex array is full.
        with self.assertRaises(ArrayIndexError):
            apex_array.append(1)

        # Get the item.
        item1 = apex_array[-1]
        # Check it's a UUID.
        self.assertIsInstance(apex_id, UUID)
        # Check it's the last things that was added above.
        self.assertEqual(item1, added[-1])

        # Check the "last array" is the apex we got above.
        last_array, i = root.get_last_array()
        self.assertEqual(last_array, apex_array)
        # Check the 'i' value of the apex is 0.
        self.assertEqual(i, 0)

        # Check the "last item" is the item we got above.
        last_item, length = root.get_last_and_len()
        self.assertEqual(last_item, added[-1])
        # Check the index of the item.
        self.assertEqual(length, 1)

        # Can add 2 items if base_size is 2.
        root, added = self.start_and_set(base_size=2, num_items=2)
        last_item, length = root.get_last_and_len()
        self.assertEqual(last_item, added[-1])
        self.assertEqual(length, 2)
        self.assertEqual(len(self.subrepo[root.id]), 1)

        # Can add 3 items if base_size is 2.
        root, added = self.start_and_set(base_size=2, num_items=3)
        last_item, length = root.get_last_and_len()
        self.assertEqual(last_item, added[-1])
        self.assertEqual(length, 3)
        self.assertEqual(len(self.subrepo[root.id]), 2)
        self.assertEqual(len(last_array), 1)

        # Check can append another, that it's not full.
        last_array.append(1)

        # Can add 4 items if base_size is 2.
        root, added = self.start_and_set(base_size=2, num_items=4)
        last_item, length = root.get_last_and_len()
        self.assertEqual(last_item, added[-1])
        self.assertEqual(length, 4)

        # Can add 6 items if base_size is 3.
        root, added = self.start_and_set(base_size=3, num_items=7)
        last_item, length = root.get_last_and_len()
        self.assertEqual(last_item, added[-1])
        self.assertEqual(length, 7)

        root, added = self.start_and_set(base_size=3, num_items=9)
        last_item, length = root.get_last_and_len()
        self.assertEqual(last_item, added[-1])
        self.assertEqual(length, 9)

        root, added = self.start_and_set(base_size=3, num_items=10)
        last_item, length = root.get_last_and_len()
        self.assertEqual(last_item, added[-1])
        self.assertEqual(length, 10)

        root, added = self.start_and_set(base_size=4, num_items=16)
        last_item, length = root.get_last_and_len()
        self.assertEqual(last_item, added[-1])
        self.assertEqual(length, 16)

        root, added = self.start_and_set(base_size=4, num_items=27)
        last_item, length = root.get_last_and_len()
        self.assertEqual(last_item, added[-1])
        self.assertEqual(length, 27)

        # Can't add 2 items if base_size is 1.
        with self.assertRaises(ArrayIndexError):
            self.start_and_set(base_size=1, num_items=2)

        # Can't add 5 items if base_size is 2.
        with self.assertRaises(ArrayIndexError):
            self.start_and_set(base_size=2, num_items=5)

        # Can't add 28 items if base_size is 3.
        with self.assertRaises(ArrayIndexError):
            self.start_and_set(base_size=3, num_items=28)

    @notquick
    def test_big_array_longer(self):
        # Can add 256 items if base_size is 4.
        self.start_and_set(base_size=4, num_items=256)

        # Can't add 257 items if base_size is 4.
        with self.assertRaises(ArrayIndexError):
            self.start_and_set(base_size=4, num_items=257)

        # Can add 100 items if base_size is 10000.
        #  - Should have capacity for 10000**10000 items,
        #    which is 1e+40000 items, but is not checked here.
        root, added = self.start_and_set(base_size=10000, num_items=100)
        self.assertEqual(root.get_last_and_len(), (added[-1], 100))
        # Check depth is 1.
        self.assertEqual(len(self.subrepo[root.id]), 1)

        # Can add 101 items if array_size is 100.
        root, added = self.start_and_set(base_size=100, num_items=101)
        self.assertEqual(root.get_last_and_len(), (added[-1], 101))
        # Check depth is 2.
        self.assertEqual(len(self.subrepo[root.id]), 2)

    def test_big_array_bigoffset(self):
        # Can add 256 items with large offset.
        base_size = 4000
        offset = 400000000000000000000000000000000000
        root, added = self.start_and_set(base_size=base_size, num_items=256, offset=offset)
        self.assertEqual(len(self.subrepo[root.id]), 10)  # depth of array tree
        self.assertEqual(len(list(self.repo[root.id][offset:])), 256)

    @notquick
    def test_big_array_biggest_offset(self):
        # Can add 25 items at the end.
        base_size = 4000
        offset = (base_size ** base_size) - 25
        root, added = self.start_and_set(base_size=base_size, num_items=25, offset=offset)
        self.assertEqual(len(self.subrepo[root.id]), base_size)  # depth of array tree
        self.assertEqual(len(list(self.repo[root.id][offset:])), 25)

    @notquick
    def test_big_array_too_much_offset(self):
        # Can't add 1 item past the end.
        base_size = 4000
        offset = (base_size ** base_size)
        with self.assertRaises(ArrayIndexError):
            self.start_and_set(base_size=base_size, num_items=1, offset=offset)

    def test_iterator_2_3(self):
        self._test_iterator(array_size=2, num_items=3)

    def test_iterator_2_4(self):
        self._test_iterator(array_size=2, num_items=3)

    def test_iterator_3_20(self):
        self._test_iterator(array_size=3, num_items=20)

    def test_iterator_3_27(self):
        self._test_iterator(array_size=3, num_items=27)

    @notquick
    def test_iterator_4_230(self):
        self._test_iterator(array_size=4, num_items=230)

    def test_iterator_1000_23(self):
        self._test_iterator(array_size=1000, num_items=23)

    def _test_iterator(self, array_size, num_items):
        array, added = self.start_and_set(array_size, num_items)

        self.assertEqual(array[0], added[0])
        self.assertEqual(array[-3], added[-3])
        self.assertEqual(array[1], added[1])
        self.assertEqual(array[-2], added[-2])
        self.assertEqual(array[2], added[2])
        self.assertEqual(array[-1], added[-1])

        # Check slices also work.
        self.assertEqual(list(array[0:3]), added[0:3])
        self.assertEqual(list(array[0:2]), added[0:2])
        self.assertEqual(list(array[0:-1]), added[0:-1])
        self.assertEqual(list(array[0:1]), added[0:1])
        self.assertEqual(list(array[0:-2]), added[0:-2])
        self.assertEqual(list(array[1:3]), added[1:3])
        self.assertEqual(list(array[1:2]), added[1:2])
        self.assertEqual(list(array[-2:-1]), added[-2:-1])
        self.assertEqual(list(array[1:1]), added[1:1])
        self.assertEqual(list(array[-2:-2]), added[-2:-2])
        self.assertEqual(list(array[2:3]), added[2:3])
        self.assertEqual(list(array[3:3]), added[3:3])
        self.assertEqual(list(array[0:300]), added[0:300])
        self.assertEqual(list(array[2:1]), added[2:1])
        self.assertEqual(list(array[2:-2]), added[2:-2])

        self.assertEqual(list(array[0:]), added[0:])
        self.assertEqual(list(array[1:]), added[1:])
        self.assertEqual(list(array[2:]), added[2:])
        self.assertEqual(list(array[3:]), added[3:])
        self.assertEqual(list(array[4:]), added[4:])
        self.assertEqual(list(array[-1:]), added[-1:])
        self.assertEqual(list(array[-2:]), added[-2:])
        self.assertEqual(list(array[-3:]), added[-3:])
        self.assertEqual(list(array[-4:]), added[-4:])

        self.assertEqual(list(array[:0]), added[:0])
        self.assertEqual(list(array[:1]), added[:1])
        self.assertEqual(list(array[:2]), added[:2])
        self.assertEqual(list(array[:3]), added[:3])
        self.assertEqual(list(array[:4]), added[:4])
        self.assertEqual(list(array[:-1]), added[:-1])
        self.assertEqual(list(array[:-2]), added[:-2])
        self.assertEqual(list(array[:-3]), added[:-3])
        self.assertEqual(list(array[:-4]), added[:-4])

        # Check iterator.
        for i, item in enumerate(array):
            self.assertEqual(item, 'item-{}'.format(i))

        # Check len.
        self.assertEqual(len(array), num_items)

        # Check index errors.
        # - out of range
        with self.assertRaises(ArrayIndexError):
            # noinspection PyStatementEffect
            array[num_items]

        with self.assertRaises(ArrayIndexError):
            # noinspection PyStatementEffect
            array[- num_items - 1]

        return array, added

    def test_setitem(self):

        a = self.get_big_array(1)
        # self.assertEqual(a.repo.array_size, 1)
        self.assertEqual(list(a[:]), [])
        a[0] = 'item-0'
        self.assertEqual(list(a[:]), ['item-0'])
        with self.assertRaises(ConcurrencyError):
            a[0] = 'item-0'

        a = self.get_big_array(2)
        a[0] = 'item-0'
        self.assertEqual(list(a[:]), ['item-0'])
        a[1] = 'item-1'
        self.assertEqual(list(a[:]), ['item-0', 'item-1'])
        a[2] = 'item-2'
        self.assertEqual(list(a[:]), ['item-0', 'item-1', 'item-2'])

        # return
        # Add four items in order to an big array with array size 4.
        a = self.get_big_array(4)

        assert isinstance(a, BigArray)
        items = []
        for i in range(4):
            item = 'item-{}'.format(i)
            a[i] = item
            items.append(item)

        self.assertEqual(list(a[:]), items)

        # Add three items in reverse order to big array with array size 4.
        a = self.get_big_array(4)
        items = []
        for i in reversed(range(1, 4)):
            item = 'item-{}'.format(i)
            a[i] = item
            items.append(item)

        self.assertEqual(list(a[:]), list(reversed(items)))

        # Check getting the first item (which wasn't set) raises IndexError.
        with self.assertRaises(ArrayIndexError):
            a[0]

        item0 = 'item-0'
        a[0] = item0
        self.assertEqual(a[0], item0)
        items.append(item0)

        # Add fifth item, which should trigger extending the compound
        # by one base array.
        a[4] = 'item-4'
        self.assertEqual(list(a[:]), list(reversed(items)) + ['item-4'])

        # Add sixth item, which should trigger extending the compound
        # by one base array.
        a[40] = 'item-40'
        # Todo: This should perhaps have 30+ None items?
        self.assertEqual(list(a[:]), list(reversed(items)) + ['item-4', 'item-40'])

        a[20] = 'item-20'
        # Todo: This should perhaps have 30+ None items?
        self.assertEqual(list(a[:]), list(reversed(items)) + ['item-4', 'item-20', 'item-40'])

        # Add item at position 200, which should trigger extending
        # the compound by several base arrays. Building a full
        # tree would be expensive, so maybe just pick out the
        # single path to the root, adding in the things in expected
        # positions, so "last" can be quite far quite quickly.

        # Add 20 items in reverse order to compound with array size 4.
        a = self.get_big_array(4)
        items = []
        for i in reversed(range(20)):
            item = 'item-{}'.format(i)
            a[i] = item
            items.append(item)

        self.assertEqual(list(a[:]), list(reversed(items)))

        # Add 20 items in shuffled order to compound with array size 4.
        a = self.get_big_array(3)
        items = []
        indexes = list(range(11))
        shuffle(indexes)
        for i in indexes:
            item = 'item-{}'.format(i)
            a[i] = item
            items.append(item)

        self.assertEqual(list(sorted(a[:])), list(sorted(reversed(items))))

    def test_calc_required_height(self):
        root = BigArray(
            array_id='1',
            repo=mock.Mock(spec=AbstractArrayRepository),
        )
        with self.assertRaises(ValueError):
            root.calc_required_height(0, 0)
        self.assertEqual(root.calc_required_height(0, 1), 1)
        with self.assertRaises(ArrayIndexError):
            root.calc_required_height(1, 1)
        self.assertEqual(root.calc_required_height(0, 2), 1)
        self.assertEqual(root.calc_required_height(1, 2), 1)
        self.assertEqual(root.calc_required_height(2, 2), 2)
        self.assertEqual(root.calc_required_height(3, 2), 2)
        with self.assertRaises(ArrayIndexError):
            root.calc_required_height(4, 2)

        self.assertEqual(root.calc_required_height(0, 3), 1)
        self.assertEqual(root.calc_required_height(1, 3), 1)
        self.assertEqual(root.calc_required_height(2, 3), 1)
        self.assertEqual(root.calc_required_height(3, 3), 2)
        self.assertEqual(root.calc_required_height(4, 3), 2)
        self.assertEqual(root.calc_required_height(5, 3), 2)
        self.assertEqual(root.calc_required_height(6, 3), 2)
        self.assertEqual(root.calc_required_height(7, 3), 2)
        self.assertEqual(root.calc_required_height(8, 3), 2)
        self.assertEqual(root.calc_required_height(9, 3), 3)
        self.assertEqual(root.calc_required_height(10, 3), 3)
        self.assertEqual(root.calc_required_height(11, 3), 3)
        self.assertEqual(root.calc_required_height(12, 3), 3)
        self.assertEqual(root.calc_required_height(13, 3), 3)
        self.assertEqual(root.calc_required_height(14, 3), 3)
        self.assertEqual(root.calc_required_height(15, 3), 3)
        self.assertEqual(root.calc_required_height(16, 3), 3)
        self.assertEqual(root.calc_required_height(17, 3), 3)
        self.assertEqual(root.calc_required_height(18, 3), 3)
        self.assertEqual(root.calc_required_height(19, 3), 3)
        self.assertEqual(root.calc_required_height(20, 3), 3)
        self.assertEqual(root.calc_required_height(21, 3), 3)
        self.assertEqual(root.calc_required_height(22, 3), 3)
        self.assertEqual(root.calc_required_height(23, 3), 3)
        self.assertEqual(root.calc_required_height(24, 3), 3)
        self.assertEqual(root.calc_required_height(25, 3), 3)
        self.assertEqual(root.calc_required_height(26, 3), 3)
        with self.assertRaises(ArrayIndexError):
            root.calc_required_height(27, 3)

        self.assertEqual(root.calc_required_height(100 ** 100 - 1, 100), 100)
        self.assertEqual(root.calc_required_height(400 ** 400 - 1, 400), 400)
        self.assertEqual(root.calc_required_height(900 ** 900 - 1, 900), 900)
        self.assertEqual(root.calc_required_height(999 ** 999 - 1, 999), 999)
        self.assertEqual(root.calc_required_height(1000 ** 1000 - 1, 1000), 1000)
        self.assertEqual(root.calc_required_height(1001 ** 1001 - 1, 1001), 1001)
        self.assertEqual(root.calc_required_height(1100 ** 1100 - 1, 1100), 1100)
        self.assertEqual(root.calc_required_height(2000 ** 2000 - 1, 2000), 2000)
        self.assertEqual(root.calc_required_height(10000 ** 10000 - 1, 10000), 10000)


class TestBigArrayWithSQLAlchemyAndMultithreading(BigArrayTestCase):
    use_named_temporary_file = True

    def setUp(self):
        super(TestBigArrayWithSQLAlchemyAndMultithreading, self).setUp()
        self.repo = BigArrayRepository(
            event_store=self.entity_event_store,
        )
        self.subrepo = self.repo.subrepo
        self.result_queue = None

    def test_compound_array_threads_1_1_1(self):
        self._test_compound_array_threads(1, 1, 1)

    def test_compound_array_threads_2_2_2(self):
        self._test_compound_array_threads(2, 2, 2)

    def test_compound_array_threads_3_3_9(self):
        self._test_compound_array_threads(3, 3, 9)

    def test_compound_array_threads_3_9_3(self):
        self._test_compound_array_threads(3, 9, 3)

    @notquick
    @skipIf(version_info[0:2] == [3, 3], "Avoid 'database is locked' error from SQLite")
    def test_compound_array_threads_4_4_64(self):
        self._test_compound_array_threads(4, 4, 64)

    @notquick
    @skipIf(version_info[0:2] == [3, 3], "Avoid 'database is locked' error from SQLite")
    def test_compound_array_threads_4_8_32(self):
        self._test_compound_array_threads(4, 8, 32)

    @notquick
    @skipIf(version_info[0:2] == [3, 3], "Avoid 'database is locked' error from SQLite")
    def test_compound_array_threads_4_16_16(self):
        self._test_compound_array_threads(4, 16, 16)

    @skip("Avoid 'database is locked' error from SQLite")
    @notquick
    def test_compound_array_threads_4_32_8(self):
        self._test_compound_array_threads(4, 32, 8)

    @skip("Avoid 'database is locked' error from SQLite")
    @notquick
    def test_compound_array_threads_4_64_4(self):
        self._test_compound_array_threads(4, 64, 4)

    @skip("Avoid 'database is locked' error from SQLite")
    @notquick
    def test_compound_array_threads_4_256_1(self):
        self._test_compound_array_threads(4, 256, 1)

    def _test_compound_array_threads(self, array_size, num_threads, num_items_per_thread):
        error_queue = Queue()
        full_queue = Queue()
        self.result_queue = Queue()
        assert num_threads * num_items_per_thread == array_size ** array_size, (
            num_threads * num_items_per_thread, array_size ** array_size)
        root = self.get_big_array(base_size=array_size)

        def task():
            try:
                for item in self.append_items(num_items_per_thread, root):
                    self.result_queue.put(item)
            except ArrayIndexError as e:
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

        expected_results = min(array_size ** array_size, num_threads * num_items_per_thread)
        self.assertEqual(len(results), expected_results)

        # Check the height of the root.
        # - limited either by the max capacity
        #   or by the number of added item

        if expected_results <= 1:
            expected_height = expected_results
        else:
            expected_height = ceil(log(expected_results, array_size))

        self.assertEqual(len(self.subrepo[root.id]), expected_height)


class TestArrayWithCassandra(WithCassandraActiveRecordStrategies, TestArrayWithSQLAlchemy):
    pass


class TestBigArrayWithCassandra(WithCassandraActiveRecordStrategies, TestBigArrayWithSQLAlchemy):
    pass


class TestBigArrayWithCassandraAndMultithreading(WithCassandraActiveRecordStrategies,
                                                 TestBigArrayWithSQLAlchemyAndMultithreading):
    pass
