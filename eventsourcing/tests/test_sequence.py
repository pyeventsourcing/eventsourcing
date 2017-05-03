from uuid import uuid4

from eventsourcing.exceptions import SequenceFullError
from eventsourcing.infrastructure.event_sourced_repos.sequence import SequenceRepo
from eventsourcing.infrastructure.sequencereader import SequenceReader
from eventsourcing.tests.sequenced_item_tests.base import WithPersistencePolicies
from eventsourcing.tests.sequenced_item_tests.test_cassandra_active_record_strategy import \
    WithCassandraActiveRecordStrategies
from eventsourcing.tests.sequenced_item_tests.test_sqlalchemy_active_record_strategy import \
    WithSQLAlchemyActiveRecordStrategies


class SequenceTestCase(WithPersistencePolicies):
    def test(self):
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


class TestCassandraSequence(WithCassandraActiveRecordStrategies, SequenceTestCase):
    pass


class TestSQLAlchemySequence(WithSQLAlchemyActiveRecordStrategies, SequenceTestCase):
    pass
