from uuid import uuid4, UUID, uuid5

from eventsourcing.domain.model.sequence import start_compound_sequence
from eventsourcing.exceptions import SequenceFullError
from eventsourcing.infrastructure.event_sourced_repos.sequence import SequenceRepo, CompoundSequenceRepo
from eventsourcing.infrastructure.sequencereader import SequenceReader
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

    def test_compound_sequence(self):
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
        root = repo.start(None, None, max_size=SEQUENCE_SIZE)

        # Check the last sequence is root.
        self.assertEqual(get_last_sequence(root), root)

        # Add child sequence ID to root.
        i = 0
        j = SEQUENCE_SIZE
        child1 = repo.start(i, j, max_size=2)
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
        child2 = repo.start(i, j, max_size=2)

        # - append to root
        root.append(child2.id)

        child2.append(child1.id)
        self.assertEqual(get_last_item(child1), 'item2')
        self.assertEqual(get_last_item(child2), 'item2')
        self.assertEqual(get_last_item(root), 'item2')

        # Now add child3 to child2.
        i = SEQUENCE_SIZE       # SEQUENCE_SIZE + i of child1
        j = 2 * SEQUENCE_SIZE   # SEQUENCE_SIZE + j of child1
        child3 = repo.start(i, j, max_size=10)
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
        child4 = repo.start(i, j, max_size=2)
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
        child6 = repo.start(i, j, max_size=2)

        child6.append('item5')
        self.assertEqual(get_last_item(root), 'item4')

        i = 2 * SEQUENCE_SIZE
        j = 4 * SEQUENCE_SIZE
        child5 = repo.start(i, j, max_size=2)
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
        child7 = repo.start(i, j, max_size=2)
        child7.append('item7')
        child5.append(child7.id)

        self.assertEqual(get_last_item(root), 'item7')

        child7.append('item8')
        self.assertEqual(get_last_item(root), 'item8')

        self.assertEqual(len(root), 3)  # 8 items

        # Now we're full again, so need to demote child4 under child8.
        i = 0
        j = 8 * SEQUENCE_SIZE
        child8 = repo.start(i, j, max_size=2)
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



class TestCassandraSequence(WithCassandraActiveRecordStrategies, SequenceTestCase):
    pass


class TestSQLAlchemySequence(WithSQLAlchemyActiveRecordStrategies, SequenceTestCase):
    pass
