from math import floor
from operator import floordiv
from uuid import uuid4, UUID, uuid5

from eventsourcing.domain.model.sequence import start_compound_sequence
from eventsourcing.exceptions import SequenceFullError, ConcurrencyError
from eventsourcing.infrastructure.event_sourced_repos.sequence import SequenceRepo, CompoundSequenceRepo
from eventsourcing.infrastructure.sequencereader import SequenceReader, CompoundSequenceReader
from eventsourcing.tests.sequenced_item_tests.base import WithPersistencePolicies
from eventsourcing.tests.sequenced_item_tests.test_cassandra_active_record_strategy import \
    WithCassandraActiveRecordStrategies
from eventsourcing.tests.sequenced_item_tests.test_sqlalchemy_active_record_strategy import \
    WithSQLAlchemyActiveRecordStrategies


class SequenceTestCase(WithPersistencePolicies):
    def _test_simple_sequence(self):
        repo = SequenceRepo(self.entity_event_store)

        # Start a new sequence.
        sequence_id = uuid4()

        # Check get_reader() can create a new sequence.
        sequence = repo.get_reader(sequence_id)
        self.assertIsInstance(sequence, SequenceReader)
        self.assertEqual(sequence.id, sequence_id)

        # Check get_reader() can return an existing sequence.
        sequence = repo.get_reader(sequence_id)
        self.assertIsInstance(sequence, SequenceReader)
        self.assertEqual(sequence.id, sequence_id)

        # Append some items.
        sequence.append('item1')
        sequence.append('item2')
        sequence.append('item3')

        # Check the sequence in the repo.
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

    def test_compound_sequence_internals(self):
        # Check that sequences can be stacked.

        repo = CompoundSequenceRepo(self.entity_event_store)

        # Start a root sequence.
        SEQUENCE_SIZE = 2

        root = repo.start_root(max_size=10)

        self.assertEqual(root.max_size, 10)
        self.assertEqual(root.i, None)
        self.assertEqual(root.j, None)
        self.assertEqual(root.h, None)

        # Check the last sequence is root.
        self.assertEqual(repo.get_last_sequence(root), root)

        # Add first child sequence to root.
        i = 0
        j = SEQUENCE_SIZE
        child1 = repo.start(root.id, i, j, 1, max_size=SEQUENCE_SIZE)
        self.assertEqual(child1.i, 0)
        self.assertEqual(child1.j, 2)
        self.assertEqual(child1.h, 1)


        self.assertEqual(child1.max_size, SEQUENCE_SIZE)
        self.assertEqual(child1.i, 0)
        self.assertEqual(child1.j, SEQUENCE_SIZE)

        # - append to root
        root.append(child1.id)
        self.assertEqual(root[0], child1.id)

        # Check the last sequence is child1.
        self.assertEqual(repo.get_last_sequence(root), child1)

        # Check the last item in the last sequence is None.
        with self.assertRaises(IndexError):
            repo.get_last_item(root)

        # Add item to child1.
        child1.append('item1')

        # Check the last item is item1.
        self.assertEqual(repo.get_last_item(child1), 'item1')
        self.assertEqual(repo.get_last_item(root), 'item1')

        # Add another item to child1.
        child1.append('item2')

        # Append and check the last item is item2.
        self.assertEqual(repo.get_last_item(child1), 'item2')
        self.assertEqual(repo.get_last_item(root), 'item2')

        self.assertEqual(len(root), 1)

        # Demote child1.
        child2 = repo.demote(root, child1)
        self.assertEqual(child2.i, 0)
        self.assertEqual(child2.j, 4)
        self.assertEqual(child2.h, 2)

        self.assertEqual(repo.get_last_item(child1), 'item2')
        self.assertEqual(repo.get_last_item(child2), 'item2')
        self.assertEqual(repo.get_last_item(root), 'item2')

        # Extend the base beyond child1.
        child3 = repo.extend_base(root.id, child1, 'item3')
        self.assertEqual(child3.i, 2)
        self.assertEqual(child3.j, 4)
        self.assertEqual(child3.h, 1)

        # Identify parent (should be child2).
        i, j, h = repo.calc_parent_i_j_h(child3)

        # Check creating parent doesn't work (already exists).
        with self.assertRaises(ConcurrencyError):
            repo.start(root.id, i, j, h, root.max_size)

        parent_id = repo.create_sequence_id(root.id, i, j)
        self.assertIn(parent_id, repo)

        parent = CompoundSequenceReader(repo[parent_id], repo.event_store)

        self.assertEqual(parent, child2)

        # Attach to parent.
        parent.append(child3.id)

        # Check the last sequence from the root is now child3.
        self.assertEqual(repo.get_last_sequence(root), child3)

        # Check the last item from the root is now item3.
        self.assertEqual(repo.get_last_item(child1), 'item2')
        self.assertEqual(repo.get_last_item(child2), 'item3')
        self.assertEqual(repo.get_last_item(child3), 'item3')
        self.assertEqual(repo.get_last_item(root), 'item3')

        # Append another item to child3.
        child3.append('item4')

        # Check the last item from the root is now item4.
        self.assertEqual(repo.get_last_item(root), 'item4')

        # Check the length of root.
        self.assertEqual(len(root), 2)  # 4 items

        # Extend the base beyond child3.
        child6 = repo.extend_base(root.id, child3, 'item5')
        self.assertEqual(child6.i, 4)
        self.assertEqual(child6.j, 6)
        self.assertEqual(child6.h, 1)

        self.assertEqual(repo.get_last_item(root), 'item4')

        # Construct detached branch.
        child5, attachment_point = repo.create_detached_branch(root.id, child6, len(root))
        self.assertEqual(child5.i, 4)
        self.assertEqual(child5.j, 8)
        self.assertEqual(child5.h, 2)

        # Attachment point is None, because we need to demote the root's child.
        self.assertIsNone(attachment_point)

        self.assertEqual(repo.get_last_item(root), 'item4')

        # Demote child2, while attaching new branch.
        child4 = repo.demote(root, child2, detached_id=child5.id)
        self.assertEqual(child4.i, 0)
        self.assertEqual(child4.j, 8)
        self.assertEqual(child4.h, 3)

        # Check the last item is correct.
        self.assertEqual(repo.get_last_item(root), 'item5')

        # Append another item.
        child6.append('item6')

        # Check the last item is correct.
        self.assertEqual(repo.get_last_item(root), 'item6')

        # Child6 is full so extend base to child7.
        child7 = repo.extend_base(root.id, child6, 'item7')
        self.assertEqual(child7.i, 6)
        self.assertEqual(child7.j, 8)
        self.assertEqual(child7.h, 1)

        # Construct detached branch.
        branch, attachment_point = repo.create_detached_branch(root.id, child7, len(root))

        # Attachment point exists.
        self.assertEqual(attachment_point, child5.id)

        # Attach branch.
        repo.attach_branch(attachment_point, branch.id)

        # Check the last item is correct.
        self.assertEqual(repo.get_last_item(root), 'item7')

        # Append another item.
        child7.append('item8')
        self.assertEqual(repo.get_last_item(root), 'item8')

        # Check the length of root.
        self.assertEqual(len(root), 3)  # 8 items

        # Now we're full again, so need can demote child4 under child8.
        child8 = repo.demote(root, child4)

        # Check the last item is correct.
        self.assertEqual(repo.get_last_item(root), 'item8')

        # Check the length of root.
        self.assertEqual(len(root), 4)  # 16 items

        # Now do it more generally...

        repo.append_item('item9', root.id)
        self.assertEqual(repo.get_last_item(root), 'item9')
        repo.append_item('item10', root.id)
        self.assertEqual(repo.get_last_item(root), 'item10')
        repo.append_item('item11', root.id)
        self.assertEqual(repo.get_last_item(root), 'item11')
        repo.append_item('item12', root.id)
        self.assertEqual(repo.get_last_item(root), 'item12')

        # Hence the depth is limited by the max_size of root.
        # The number of items at a given depth is max_size
        # to the power of the depth.
        # Hence it is possible to store max_size**max_size
        # items in a compound sequence made from sequences
        # of max_size. So if max_size is 1000, which would
        # easily fit in a partition, the number items would
        # be 10**3000 items, which is probably enough.


    def test_compound_sequence_api(self):
        repo = CompoundSequenceRepo(self.entity_event_store)

        def start_and_add_items(max_size, num_items):
            if num_items == 0:
                return
            root = repo.start_root_with_item(max_size=max_size, item='item0')
            for i in range(1, num_items):
                item = 'item{}'.format(i)
                repo.append_item(item, root.id)

        # Can add zero items if max_size is zero.
        start_and_add_items(0, 0)

        # Todo: This should pass, but somehow it raises the wrong exception (ConcurrencyError).
        # # Can't add 1 items if max_size is 0.
        # with self.assertRaises(SequenceFullError):
        #     start_and_add_items(max_size=1, num_items=2)

        # Can add zero items if max_size is 1.
        start_and_add_items(1, 0)

        # Can add 1 items if max_size is 1.
        start_and_add_items(max_size=1, num_items=1)

        # Todo: This should pass, but somehow it raises the wrong exception (ConcurrencyError).
        # Can't add 2 items if max_size is 1.
        # with self.assertRaises(SequenceFullError):
        #     start_and_add_items(max_size=1, num_items=2)

        # Can add 4 items if max_size is 2.
        start_and_add_items(max_size=2, num_items=4)

        # Can't add 5 items if max_size is 2.
        with self.assertRaises(SequenceFullError):
            start_and_add_items(max_size=2, num_items=5)

        # Can add 27 items if max_size is 3.
        start_and_add_items(max_size=3, num_items=27)

        # Can't add 28 items if max_size is 3.
        with self.assertRaises(SequenceFullError):
            start_and_add_items(max_size=3, num_items=28)

        # # Can add 256 items if max_size is 4.
        # start_and_add_items(max_size=4, num_items=256)
        #
        # # Can't add 257 items if max_size is 4.
        # with self.assertRaises(SequenceFullError):
        #     start_and_add_items(max_size=4, num_items=257)

        # # Can add 3125 items if max_size is 5.
        # start_and_add_items(max_size=5, num_items=3125)
        #
        # # Can't add 3126 items if max_size is 5.
        # with self.assertRaises(SequenceFullError):
        #     start_and_add_items(max_size=5, num_items=3126)
        #

        # Can add 100 items if max_size is 10000.
        # - should be room for 10000**10000 items, but not going to check that here
        start_and_add_items(max_size=10000, num_items=100)
        pass



class TestCassandraSequence(WithCassandraActiveRecordStrategies, SequenceTestCase):
    pass


class TestSQLAlchemySequence(WithSQLAlchemyActiveRecordStrategies, SequenceTestCase):
    pass
