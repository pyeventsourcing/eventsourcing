from uuid import uuid4

from eventsourcing.exceptions import ConcurrencyError, SequenceFullError
from eventsourcing.infrastructure.event_sourced_repos.sequence import CompoundSequenceRepository, SequenceRepo
from eventsourcing.infrastructure.sequencereader import CompoundSequenceReader, SequenceReader
from eventsourcing.tests.base import notquick
from eventsourcing.tests.sequenced_item_tests.base import WithPersistencePolicies
from eventsourcing.tests.sequenced_item_tests.test_cassandra_active_record_strategy import \
    WithCassandraActiveRecordStrategies
from eventsourcing.tests.sequenced_item_tests.test_sqlalchemy_active_record_strategy import \
    WithSQLAlchemyActiveRecordStrategies


class SequenceTestCase(WithPersistencePolicies):
    def setUp(self):
        super(SequenceTestCase, self).setUp()
        self.repo = SequenceRepo(self.entity_event_store)

    def test_simple_sequence(self):

        # Start a new sequence.
        sequence_id = uuid4()

        # Check get_reader() can create a new sequence.
        sequence = self.repo.get_reader(sequence_id)
        self.assertIsInstance(sequence, SequenceReader)
        self.assertEqual(sequence.id, sequence_id)

        # Check get_reader() can return an existing sequence.
        sequence = self.repo.get_reader(sequence_id)
        self.assertIsInstance(sequence, SequenceReader)
        self.assertEqual(sequence.id, sequence_id)

        # Append some items.
        sequence.append('item1')
        sequence.append('item2')
        sequence.append('item3')

        # Check the sequence in the self.repo.
        self.assertIsInstance(sequence, SequenceReader)
        self.assertEqual(sequence.id, sequence_id)

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

        # Check iterator.
        for i, item in enumerate(sequence):
            self.assertEqual(item, 'item{}'.format(i + 1))

        # Check len.
        self.assertEqual(len(sequence), 3)

        # Check index errors.
        # - out of range
        with self.assertRaises(IndexError):
            # noinspection PyStatementEffect
            sequence[3]

        with self.assertRaises(IndexError):
            # noinspection PyStatementEffect
            sequence[-4]

        with self.assertRaises(SequenceFullError):
            # Append another item.
            sequence.max_size = 1
            sequence.append('item1')

# Todo: Test with multiple threads trying to append items
# at the same time. It should work, but does need testing.

class CompoundSequenceTestCase(WithPersistencePolicies):

    def setUp(self):
        super(CompoundSequenceTestCase, self).setUp()
        self.repo = CompoundSequenceRepository(self.entity_event_store)

    def test_compound_sequence_internals(self):
        # Check that sequences can be stacked.

        self.repo = CompoundSequenceRepository(self.entity_event_store)

        # Start a root sequence.
        SEQUENCE_SIZE = 2

        root = self.repo.start_root(max_size=2)

        # Just make this a bit bigger for the test,
        # because debugging is simpler with sequence
        # size of 2, but need a deeper compound to
        # check the basic operations.
        root.max_size = 10

        self.assertEqual(root.max_size, 10)
        self.assertEqual(root.i, None)
        self.assertEqual(root.j, None)
        self.assertEqual(root.h, None)

        # Check the first sequence.
        child1 = self.repo.get_last_sequence(root)

        self.assertEqual(child1.i, 0)
        self.assertEqual(child1.j, 2)
        self.assertEqual(child1.h, 1)

        self.assertEqual(child1.max_size, SEQUENCE_SIZE)
        self.assertEqual(child1.i, 0)
        self.assertEqual(child1.j, SEQUENCE_SIZE)

        self.assertEqual(root[0], child1.id)

        # Check the last sequence is child1.
        self.assertEqual(self.repo.get_last_sequence(root), child1)

        # Check the last item in the last sequence is None.
        with self.assertRaises(IndexError):
            self.repo.get_last_item(root)

        # Add item to child1.
        child1.append('item1')

        # Check the last item is item1.
        self.assertEqual(self.repo.get_last_item(child1), 'item1')
        self.assertEqual(self.repo.get_last_item(root), 'item1')

        # Add another item to child1.
        child1.append('item2')

        # Append and check the last item is item2.
        self.assertEqual(self.repo.get_last_item(child1), 'item2')
        self.assertEqual(self.repo.get_last_item(root), 'item2')

        self.assertEqual(len(root), 1)

        # Demote child1.
        child2 = self.repo.demote(root, child1)
        self.assertEqual(child2.i, 0)
        self.assertEqual(child2.j, 4)
        self.assertEqual(child2.h, 2)

        self.assertEqual(self.repo.get_last_item(child1), 'item2')
        self.assertEqual(self.repo.get_last_item(child2), 'item2')
        self.assertEqual(self.repo.get_last_item(root), 'item2')

        # Extend the base beyond child1.
        child3 = self.repo.extend_base(root.id, child1, 'item3')
        self.assertEqual(child3.i, 2)
        self.assertEqual(child3.j, 4)
        self.assertEqual(child3.h, 1)

        # Identify parent (should be child2).
        i, j, h = self.repo.calc_parent_i_j_h(child3)

        # Check creating parent doesn't work (already exists).
        with self.assertRaises(ConcurrencyError):
            self.repo.start(root.id, i, j, h, root.max_size)

        parent_id = self.repo.create_sequence_id(root.id, i, j)
        self.assertIn(parent_id, self.repo)

        parent = CompoundSequenceReader(self.repo[parent_id], self.repo.event_store)

        self.assertEqual(parent, child2)

        # Attach to parent.
        parent.append(child3.id)

        # Check the last sequence from the root is now child3.
        self.assertEqual(self.repo.get_last_sequence(root), child3)

        # Check the last item from the root is now item3.
        self.assertEqual(self.repo.get_last_item(child1), 'item2')
        self.assertEqual(self.repo.get_last_item(child2), 'item3')
        self.assertEqual(self.repo.get_last_item(child3), 'item3')
        self.assertEqual(self.repo.get_last_item(root), 'item3')

        # Append another item to child3.
        child3.append('item4')

        # Check the last item from the root is now item4.
        self.assertEqual(self.repo.get_last_item(root), 'item4')

        # Check the length of root.
        self.assertEqual(len(root), 2)  # 4 items

        # Extend the base beyond child3.
        child6 = self.repo.extend_base(root.id, child3, 'item5')
        self.assertEqual(child6.i, 4)
        self.assertEqual(child6.j, 6)
        self.assertEqual(child6.h, 1)

        self.assertEqual(self.repo.get_last_item(root), 'item4')

        # Construct detached branch.
        child5, attachment_point = self.repo.create_detached_branch(root.id, child6, len(root))
        self.assertEqual(child5.i, 4)
        self.assertEqual(child5.j, 8)
        self.assertEqual(child5.h, 2)

        # Attachment point is None, because we need to demote the root's child.
        self.assertIsNone(attachment_point)

        self.assertEqual(self.repo.get_last_item(root), 'item4')

        # Demote child2, while attaching new branch.
        child4 = self.repo.demote(root, child2, detached_id=child5.id)
        self.assertEqual(child4.i, 0)
        self.assertEqual(child4.j, 8)
        self.assertEqual(child4.h, 3)

        # Check the last item is correct.
        self.assertEqual(self.repo.get_last_item(root), 'item5')

        # Append another item.
        child6.append('item6')

        # Check the last item is correct.
        self.assertEqual(self.repo.get_last_item(root), 'item6')

        # Child6 is full so extend base to child7.
        child7 = self.repo.extend_base(root.id, child6, 'item7')
        self.assertEqual(child7.i, 6)
        self.assertEqual(child7.j, 8)
        self.assertEqual(child7.h, 1)

        # Construct detached branch.
        branch, attachment_point = self.repo.create_detached_branch(root.id, child7, len(root))

        # Attachment point exists.
        self.assertEqual(attachment_point, child5.id)

        # Attach branch.
        self.repo.attach_branch(attachment_point, branch)

        # Check the last item is correct.
        self.assertEqual(self.repo.get_last_item(root), 'item7')

        # Append another item.
        child7.append('item8')
        self.assertEqual(self.repo.get_last_item(root), 'item8')

        # Check the length of root.
        self.assertEqual(len(root), 3)  # 8 items

        # Now we're full again, so need can demote child4 under child8.
        child8 = self.repo.demote(root, child4)
        self.assertEqual(child8.i, 0)
        self.assertEqual(child8.j, 16)
        self.assertEqual(child8.h, 4)

        # Check the last item is correct.
        self.assertEqual(self.repo.get_last_item(root), 'item8')

        # Check the length of root.
        self.assertEqual(len(root), 4)  # 16 items

        # Now do it more generally...
        self.repo.append_item('item9', root.id)
        self.assertEqual(self.repo.get_last_item(root), 'item9')
        self.repo.append_item('item10', root.id)
        self.assertEqual(self.repo.get_last_item(root), 'item10')
        self.repo.append_item('item11', root.id)
        self.assertEqual(self.repo.get_last_item(root), 'item11')
        self.repo.append_item('item12', root.id)
        self.assertEqual(self.repo.get_last_item(root), 'item12')

    def start_and_append(self, max_size, num_items):
        root = self.repo.start_root(max_size=max_size)
        item = None
        if num_items == 0:
            return
        for i in range(num_items):
            # item = 'item{}'.format(i)
            item = uuid4()
            self.repo.append_item(item, root.id)
        return root, item

    def test_compound_sequence_short(self):
        # Can add zero items if max_size is zero.
        self.start_and_append(0, 0)

        # Can add zero items if max_size is 1.
        self.start_and_append(1, 0)

        # Can add 1 items if max_size is 1.
        self.start_and_append(max_size=1, num_items=1)

        # Can't add 2 items if max_size is 1.
        with self.assertRaises(SequenceFullError):
            self.start_and_append(max_size=1, num_items=2)

        # Can add 4 items if max_size is 2.
        root, last_added = self.start_and_append(max_size=2, num_items=4)

        self.assertEqual(self.repo.get_last_item(root), last_added)

        # Can't add 5 items if max_size is 2.
        with self.assertRaises(SequenceFullError):
            self.start_and_append(max_size=2, num_items=5)

        # Can add 27 items if max_size is 3.
        root, last_added = self.start_and_append(max_size=3, num_items=27)
        self.assertEqual(self.repo.get_last_item(root), last_added)

        # Can't add 28 items if max_size is 3.
        with self.assertRaises(SequenceFullError):
            self.start_and_append(max_size=3, num_items=28)

    @notquick
    def test_compound_sequence_long(self):
        # Can add 256 items if max_size is 4.
        self.start_and_append(max_size=4, num_items=256)

        # Can't add 257 items if max_size is 4.
        with self.assertRaises(SequenceFullError):
            self.start_and_append(max_size=4, num_items=257)

        # Can add 100 items if max_size is 10000.
        #  - Should have capacity for 10000**10000 items,
        #    which is 1e+40000 items, but is not checked here.
        root, last_added = self.start_and_append(max_size=10000, num_items=100)
        self.assertEqual(self.repo.get_last_item(root), last_added)
        # Check depth is 1.
        self.assertEqual(len(root), 1)

        # Can add 101 items if max_size is 100.
        root, last_added = self.start_and_append(max_size=100, num_items=101)
        self.assertEqual(self.repo.get_last_item(root), last_added)
        # Check depth is 2.
        self.assertEqual(len(root), 2)


class TestSequenceWithCassandra(WithCassandraActiveRecordStrategies, SequenceTestCase):
    pass


class TestSequenceWithSQLAlchemy(WithSQLAlchemyActiveRecordStrategies, SequenceTestCase):
    pass


class TestCompoundSequenceWithCassandra(WithCassandraActiveRecordStrategies, CompoundSequenceTestCase):
    pass


class TestCompoundSequenceWithSQLAlchemy(WithSQLAlchemyActiveRecordStrategies, CompoundSequenceTestCase):
    pass
