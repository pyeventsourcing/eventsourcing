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

    def _test_compound_sequence__sketch_only(self):
        # Check that sequences can be stacked.

        repo = SequenceRepo(self.entity_event_store)

        def get_last_sequence(sequence):
            try:
                last = sequence[-1]
            except IndexError:
                return sequence
            else:
                if isinstance(last, UUID):
                    return get_last_sequence(repo.get_reader(last))
                else:
                    return sequence

        def get_last_item(sequence):
            last_sequence = get_last_sequence(sequence)
            return last_sequence[-1]

        # Start a root sequence.
        root_id = uuid4()
        root = repo.get_reader(root_id, max_size=10)

        # Check the last sequence is root.
        self.assertEqual(get_last_sequence(root), root)

        # Add child sequence ID to root.
        child1_id = uuid4()
        # - append to root
        root.append(child1_id)
        self.assertEqual(root[0], child1_id)

        # Check the last sequence is root.
        self.assertEqual(get_last_sequence(root), repo.get_reader(child1_id))

        # Check the last item in the last sequence is None.
        with self.assertRaises(IndexError):
            get_last_item(root)

        # Add item to child1.
        child1 = repo.get_reader(child1_id, max_size=2)
        child1.append('item1')

        # Check the last item is item1.
        self.assertEqual(get_last_item(child1), 'item1')
        self.assertEqual(get_last_item(root), 'item1')

        # Add another item to child1.
        child1.append('item2')

        # Append and check the last item is item2.
        self.assertEqual(get_last_item(child1), 'item2')
        self.assertEqual(get_last_item(root), 'item2')

        self.assertEqual(len(root), 1)

        # Assume child1 is now full. Since root points
        # directly to child1, to continue adding
        # items below the root, we must add another
        # sequence to the root.

        # Let's append child2 to the root, which will be a
        # sequence of sequences. And demote child1 below child2
        # as its first sequence.
        child2_id = uuid4()

        # - append to root
        root.append(child2_id)

        child2 = repo.get_reader(child2_id, max_size=2)
        child2.append(child1_id)
        self.assertEqual(get_last_item(child1), 'item2')
        self.assertEqual(get_last_item(child2), 'item2')
        self.assertEqual(get_last_item(root), 'item2')

        # Now add child3 to child2.
        child3_id = uuid4()
        child2.append(child3_id)

        # Check the last sequence from the root is now child3.
        child3 = get_last_sequence(root)
        self.assertEqual(child3.id, child3_id)

        # Append an item to child3.
        child3.append('item3')

        # Check the last item from the root is now item3.
        self.assertEqual(get_last_item(child1), 'item2')
        self.assertEqual(get_last_item(child2), 'item3')
        self.assertEqual(get_last_item(child3), 'item3')
        self.assertEqual(get_last_item(root), 'item3')

        # Append another item to child3.
        child3.append('item4')

        # Check the last item from the root is now item4.
        self.assertEqual(get_last_item(root), 'item4')

        self.assertEqual(len(root), 2)  # 4 items

        # Assume child1 and child3 are now full of items, and child2
        # is full of sequences. Since root points
        # directly to child2, to continue adding
        # items below the root, we must add a child4
        # to the root, demote child2.
        child4_id = uuid4()
        child4 = repo.get_reader(child4_id, max_size=2)
        self.assertEqual(get_last_item(root), 'item4')
        child4.append(child2_id)
        self.assertEqual(get_last_item(root), 'item4')
        # - append to root
        root.append(child4_id)
        self.assertEqual(get_last_item(root), 'item4')

        # Now we add child5 to child4, and child6 to child5,
        # after adding an item to child6.
        child6_id = uuid4()
        child6 = repo.get_reader(child6_id, max_size=2)
        child6.append('item5')
        self.assertEqual(get_last_item(root), 'item4')

        child5_id = uuid4()
        child5 = repo.get_reader(child5_id, max_size=2)
        child5.append(child6_id)
        self.assertEqual(get_last_item(root), 'item4')

        child4.append(child5_id)
        self.assertEqual(get_last_item(root), 'item5')
        #
        # Then more items can be added to child6.
        child6.append('item6')
        self.assertEqual(get_last_item(root), 'item6')

        # When child6 is full and then items added to child7
        # and child7 added to child 5.
        child7_id = uuid4()
        child7 = repo.get_reader(child7_id, max_size=2)
        child7.append('item7')
        child5.append(child7_id)

        self.assertEqual(get_last_item(root), 'item7')

        child7.append('item8')
        self.assertEqual(get_last_item(root), 'item8')

        self.assertEqual(len(root), 3)  # 8 items

        # Now we're full again, so need to demote child4 under child8.
        child8_id = uuid4()
        child8 = repo.get_reader(child8_id, max_size=2)
        child8.append(child4_id)
        self.assertEqual(get_last_item(root), 'item8')
        # - append to root
        root.append(child8_id)
        self.assertEqual(len(root), 4)  # 16 items

        # Hence the depth is limited by the max_size of root.
        # The number of items at a given depth is max_size
        # to the power of the depth.
        # Hence it is possible to store max_size**max_size
        # items in a compound sequence made from sequences
        # of max_size. So if max_size is 1000, which would
        # easily fit in a partition, the number items would
        # be 10**3000 items, which is probably enough.

    def _test_compound_sequence(self):
        # Check that sequences can be stacked.

        repo = CompoundSequenceRepo(self.entity_event_store)

        def get_last_sequence(sequence):
            try:
                last = sequence[-1]
            except IndexError:
                return sequence
            else:
                if isinstance(last, UUID):
                    return get_last_sequence(repo.get_reader(last))
                else:
                    return sequence

        def get_last_item(sequence):
            last_sequence = get_last_sequence(sequence)
            return last_sequence[-1]

        # Start a root sequence.
        SEQUENCE_SIZE = 10

        root = repo.start(None, None, None, max_size=SEQUENCE_SIZE)

        self.assertEqual(root.max_size, SEQUENCE_SIZE)
        self.assertEqual(root.i, None)
        self.assertEqual(root.j, None)
        self.assertEqual(root.h, None)

        # Check the last sequence is root.
        self.assertEqual(get_last_sequence(root), root)

        # Add child sequence ID to root.
        i = 0
        j = SEQUENCE_SIZE
        child1 = repo.start(i, j, 0, max_size=SEQUENCE_SIZE)

        self.assertEqual(root.max_size, SEQUENCE_SIZE)
        self.assertEqual(child1.i, 0)
        self.assertEqual(child1.j, SEQUENCE_SIZE)

        # - append to root
        root.append(child1.id)
        self.assertEqual(root[0], child1.id)

        # Check the last sequence is root.
        self.assertEqual(get_last_sequence(root), repo.get_reader(child1.id))

        # Check the last item in the last sequence is None.
        with self.assertRaises(IndexError):
            get_last_item(root)

        # Add item to child1.
        child1.append('item1')

        # Check the last item is item1.
        self.assertEqual(get_last_item(child1), 'item1')
        self.assertEqual(get_last_item(root), 'item1')

        # Add another item to child1.
        child1.append('item2')

        # Append and check the last item is item2.
        self.assertEqual(get_last_item(child1), 'item2')
        self.assertEqual(get_last_item(root), 'item2')

        self.assertEqual(len(root), 1)

        # Assume child1 is now full. Since root points
        # directly to child1, to continue adding
        # items below the root, we must add another
        # sequence to the root.

        # Let's append child2 to the root, which will be a
        # sequence of sequences. And demote child1 below child2
        # as its first sequence.
        i = 0                   # same i as child1
        j = 2 * SEQUENCE_SIZE   # double j as child1
        h = child1.h + 1
        child2 = repo.start(i, j, h, max_size=2)

        # - append to root
        root.append(child2.id)

        child2.append(child1.id)
        self.assertEqual(get_last_item(child1), 'item2')
        self.assertEqual(get_last_item(child2), 'item2')
        self.assertEqual(get_last_item(root), 'item2')

        # Now add child3 to child2.
        i = SEQUENCE_SIZE
        j = 2 * SEQUENCE_SIZE
        h = child2.h - 1
        child3 = repo.start(i, j, h, max_size=10)
        child2.append(child3.id)

        # Check the last sequence from the root is now child3.
        self.assertEqual(get_last_sequence(root), child3)

        # Append an item to child3.
        child3.append('item3')

        # Check the last item from the root is now item3.
        self.assertEqual(get_last_item(child1), 'item2')
        self.assertEqual(get_last_item(child2), 'item3')
        self.assertEqual(get_last_item(child3), 'item3')
        self.assertEqual(get_last_item(root), 'item3')

        # Append another item to child3.
        child3.append('item4')

        # Check the last item from the root is now item4.
        self.assertEqual(get_last_item(root), 'item4')

        self.assertEqual(len(root), 2)  # 4 items

        # Assume child1 and child3 are now full of items, and child2
        # is full of sequences. Since root points
        # directly to child2, to continue adding
        # items below the root, we must add a child4
        # to the root, demote child2.
        i = 0
        j = 4 * SEQUENCE_SIZE
        h = child2.h + 1
        child4 = repo.start(i, j, h, max_size=2)
        self.assertEqual(get_last_item(root), 'item4')
        child4.append(child2.id)
        self.assertEqual(get_last_item(root), 'item4')
        # - append to root
        root.append(child4.id)
        self.assertEqual(get_last_item(root), 'item4')

        # Now we add child5 to child4, and child6 to child5,
        # after adding an item to child6.
        i = 2 * SEQUENCE_SIZE
        j = 3 * SEQUENCE_SIZE
        h = 0
        child6 = repo.start(i, j, h, max_size=2)

        child6.append('item5')
        self.assertEqual(get_last_item(root), 'item4')

        i = 2 * SEQUENCE_SIZE
        j = 4 * SEQUENCE_SIZE
        h = child6.h + 1
        child5 = repo.start(i, j, h, max_size=2)
        child5.append(child6.id)
        self.assertEqual(get_last_item(root), 'item4')

        child4.append(child5.id)
        self.assertEqual(get_last_item(root), 'item5')
        #
        # Then more items can be added to child6.
        child6.append('item6')
        self.assertEqual(get_last_item(root), 'item6')

        # When child6 is full and then items added to child7
        # and child7 added to child 5.
        i = 3 * SEQUENCE_SIZE
        j = 4 * SEQUENCE_SIZE
        h = 0
        child7 = repo.start(i, j, h, max_size=2)
        child7.append('item7')
        child5.append(child7.id)

        self.assertEqual(get_last_item(root), 'item7')

        child7.append('item8')
        self.assertEqual(get_last_item(root), 'item8')

        self.assertEqual(len(root), 3)  # 8 items

        # Now we're full again, so need to demote child4 under child8.
        i = 0
        j = 8 * SEQUENCE_SIZE
        h = child4.h + 1
        child8 = repo.start(i, j, h, max_size=2)
        child8.append(child4.id)
        self.assertEqual(get_last_item(root), 'item8')
        # - append to root
        root.append(child8.id)
        self.assertEqual(len(root), 4)  # 16 items

        # Hence the depth is limited by the max_size of root.
        # The number of items at a given depth is max_size
        # to the power of the depth.
        # Hence it is possible to store max_size**max_size
        # items in a compound sequence made from sequences
        # of max_size. So if max_size is 1000, which would
        # easily fit in a partition, the number items would
        # be 10**3000 items, which is probably enough.

    def _test_compound_sequence2(self):
        # Check that sequences can be stacked.

        repo = CompoundSequenceRepo(self.entity_event_store)

        # Start a root sequence.
        SEQUENCE_SIZE = 2

        root = repo.start(None, None, None, max_size=10)

        self.assertEqual(root.max_size, 10)
        self.assertEqual(root.i, None)
        self.assertEqual(root.j, None)
        self.assertEqual(root.h, None)

        # Check the last sequence is root.
        self.assertEqual(repo.get_last_sequence(root), root)

        # Add first child sequence to root.
        i = 0
        j = SEQUENCE_SIZE
        child1 = repo.start(i, j, 1, max_size=SEQUENCE_SIZE)

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

        self.assertEqual(repo.get_last_item(child1), 'item2')
        self.assertEqual(repo.get_last_item(child2), 'item2')
        self.assertEqual(repo.get_last_item(root), 'item2')

        # Extend the base beyond child1.
        child3 = repo.extend_base(child1, 'item3')

        # Identify parent (should be child2).
        i, j, h = repo.calc_parent_i_j_h(child3)

        # Check creating parent doesn't work.
        with self.assertRaises(ConcurrencyError):
            repo.start(i, j, h)

        parent_id = repo.create_sequence_id(i, j)
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
        child6 = repo.extend_base(child3, 'item5')

        self.assertEqual(repo.get_last_item(root), 'item4')

        # Construct detached branch.
        child5, attachment_point = repo.create_detached_branch(child6)

        # Attach child to parent.
        # child5.append(child6.id)
        self.assertEqual(repo.get_last_item(root), 'item4')

        # Demote child2, while attaching new branch.
        child4 = repo.demote(root, child2, detached_id=child5.id)

        # Check the last item is correct.
        self.assertEqual(repo.get_last_item(root), 'item5')

        # Append another item.
        child6.append('item6')

        # Check the last item is correct.
        self.assertEqual(repo.get_last_item(root), 'item6')

        # Child6 is full so extend base to child7.
        child7 = repo.extend_base(child6, 'item7')

        # Construct detached branch.
        branch, attachment_point = repo.create_detached_branch(child7)

        # Immediate parent already exists, so don't need to attach a new branch.
        self.assertEqual(branch, child7)

        self.assertEqual(attachment_point, child5.id)

        # Append branch to attachment point.
        parent = CompoundSequenceReader(repo[attachment_point], repo.event_store)
        parent.append(branch.id)

        # Check the last item is correct.
        self.assertEqual(repo.get_last_item(root), 'item7')

        # Append another item.
        child7.append('item8')
        self.assertEqual(repo.get_last_item(root), 'item8')

        # Check the length of root.
        self.assertEqual(len(root), 3)  # 8 items

        # Now we're full again, so need to demote child4 under child8.
        child8 = repo.demote(root, child4)

        # Check the last item is correct.
        self.assertEqual(repo.get_last_item(root), 'item8')

        # Check the length of root.
        self.assertEqual(len(root), 4)  # 16 items

        # Hence the depth is limited by the max_size of root.
        # The number of items at a given depth is max_size
        # to the power of the depth.
        # Hence it is possible to store max_size**max_size
        # items in a compound sequence made from sequences
        # of max_size. So if max_size is 1000, which would
        # easily fit in a partition, the number items would
        # be 10**3000 items, which is probably enough.

    def test_compound_sequence3(self):
        # Check that sequences can be stacked.

        repo = CompoundSequenceRepo(self.entity_event_store)

        # Start a root sequence.
        SEQUENCE_SIZE = 2

        root = repo.start(None, None, None, max_size=10)

        self.assertEqual(root.max_size, 10)
        self.assertEqual(root.i, None)
        self.assertEqual(root.j, None)
        self.assertEqual(root.h, None)

        # Check the last sequence is root.
        self.assertEqual(repo.get_last_sequence(root), root)

        # Add first child sequence to root.
        i = 0
        j = SEQUENCE_SIZE
        child1 = repo.start(i, j, 1, max_size=SEQUENCE_SIZE)
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
        child3 = repo.extend_base(child1, 'item3')
        self.assertEqual(child3.i, 2)
        self.assertEqual(child3.j, 4)
        self.assertEqual(child3.h, 1)


        # Identify parent (should be child2).
        i, j, h = repo.calc_parent_i_j_h(child3)

        # Check creating parent doesn't work.
        with self.assertRaises(ConcurrencyError):
            repo.start(i, j, h)

        parent_id = repo.create_sequence_id(i, j)
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
        child6 = repo.extend_base(child3, 'item5')
        self.assertEqual(child6.i, 4)
        self.assertEqual(child6.j, 6)
        self.assertEqual(child6.h, 1)


        self.assertEqual(repo.get_last_item(root), 'item4')

        # Construct detached branch.
        child5, attachment_point = repo.create_detached_branch(child6, len(root))
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
        child7 = repo.extend_base(child6, 'item7')
        self.assertEqual(child7.i, 6)
        self.assertEqual(child7.j, 8)
        self.assertEqual(child7.h, 1)

        # Construct detached branch.
        branch, attachment_point = repo.create_detached_branch(child7, len(root))

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

        # Now we're full again, so need to demote child4 under child8.
        child8 = repo.demote(root, child4)

        # Check the last item is correct.
        self.assertEqual(repo.get_last_item(root), 'item8')

        # Check the length of root.
        self.assertEqual(len(root), 4)  # 16 items

        # Hence the depth is limited by the max_size of root.
        # The number of items at a given depth is max_size
        # to the power of the depth.
        # Hence it is possible to store max_size**max_size
        # items in a compound sequence made from sequences
        # of max_size. So if max_size is 1000, which would
        # easily fit in a partition, the number items would
        # be 10**3000 items, which is probably enough.


class TestCassandraSequence(WithCassandraActiveRecordStrategies, SequenceTestCase):
    pass


class TestSQLAlchemySequence(WithSQLAlchemyActiveRecordStrategies, SequenceTestCase):
    pass
