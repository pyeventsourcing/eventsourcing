from uuid import uuid4

from eventsourcing.domain.model.sequence import Sequence
from eventsourcing.exceptions import SequenceFullError
from eventsourcing.infrastructure.event_sourced_repos.sequence import SequenceRepo
from eventsourcing.infrastructure.sequence import SequenceReader, append_item_to_sequence
from eventsourcing.tests.sequenced_item_tests.base import WithPersistencePolicies
from eventsourcing.tests.sequenced_item_tests.test_cassandra_active_record_strategy import \
    WithCassandraActiveRecordStrategies
from eventsourcing.tests.sequenced_item_tests.test_sqlalchemy_active_record_strategy import \
    WithSQLAlchemyActiveRecordStrategies


class SequenceTestCase(WithPersistencePolicies):
    def test(self):
        repo = SequenceRepo(self.entity_event_store)

        # Start a new sequence.
        name = uuid4()

        # Check get_or_create() can create a new sequence.
        sequence = repo.get_or_create(name)
        self.assertIsInstance(sequence, Sequence)
        self.assertEqual(sequence.name, name)

        # Check get_or_create() can return an existing sequence.
        sequence = repo.get_or_create(name)
        self.assertIsInstance(sequence, Sequence)
        self.assertEqual(sequence.name, name)

        # Append some items.
        append_item_to_sequence(name, 'item1', repo.event_player)
        append_item_to_sequence(name, 'item2', repo.event_player)
        append_item_to_sequence(name, 'item3', repo.event_player)

        # Check the sequence in the repo.
        sequence = repo[name]
        self.assertIsInstance(sequence, Sequence)
        self.assertEqual(sequence.name, name)
        self.assertEqual(sequence.version, 1)

        # Check the sequence indexing.
        reader = SequenceReader(sequence, repo.event_player)
        self.assertEqual(reader[0], 'item1')
        self.assertEqual(reader[-3], 'item1')
        self.assertEqual(reader[1], 'item2')
        self.assertEqual(reader[-2], 'item2')
        self.assertEqual(reader[2], 'item3')
        self.assertEqual(reader[-1], 'item3')

        # Check slices also work.
        self.assertEqual(reader[0:3], ['item1', 'item2', 'item3'])
        self.assertEqual(reader[0:2], ['item1', 'item2'])
        self.assertEqual(reader[0:-1], ['item1', 'item2'])
        self.assertEqual(reader[0:1], ['item1'])
        self.assertEqual(reader[0:-2], ['item1'])
        self.assertEqual(reader[1:3], ['item2', 'item3'])
        self.assertEqual(reader[1:2], ['item2'])
        self.assertEqual(reader[-2:-1], ['item2'])
        self.assertEqual(reader[1:1], [])
        self.assertEqual(reader[-2:-2], [])
        self.assertEqual(reader[2:3], ['item3'])
        self.assertEqual(reader[3:3], [])
        self.assertEqual(reader[0:300], ['item1', 'item2', 'item3'])
        self.assertEqual(reader[2:1], [])
        self.assertEqual(reader[2:-2], [])

        self.assertEqual(reader[0:], ['item1', 'item2', 'item3'])
        self.assertEqual(reader[1:], ['item2', 'item3'])
        self.assertEqual(reader[2:], ['item3'])
        self.assertEqual(reader[3:], [])
        self.assertEqual(reader[4:], [])
        self.assertEqual(reader[-1:], ['item3'])
        self.assertEqual(reader[-2:], ['item2', 'item3'])
        self.assertEqual(reader[-3:], ['item1', 'item2', 'item3'])
        self.assertEqual(reader[-4:], ['item1', 'item2', 'item3'])

        self.assertEqual(reader[:0], [])
        self.assertEqual(reader[:1], ['item1'])
        self.assertEqual(reader[:2], ['item1', 'item2'])
        self.assertEqual(reader[:3], ['item1', 'item2', 'item3'])
        self.assertEqual(reader[:4], ['item1', 'item2', 'item3'])
        self.assertEqual(reader[:-1], ['item1', 'item2'])
        self.assertEqual(reader[:-2], ['item1'])
        self.assertEqual(reader[:-3], [])
        self.assertEqual(reader[:-4], [])

        # Check iterator.
        for i, item in enumerate(reader):
            self.assertEqual(item, 'item{}'.format(i + 1))

        # Check len.
        self.assertEqual(len(reader), 3)

        # Check index errors.
        # - out of range
        with self.assertRaises(IndexError):
            # noinspection PyStatementEffect
            reader[3]

        with self.assertRaises(IndexError):
            # noinspection PyStatementEffect
            reader[-4]

        with self.assertRaises(SequenceFullError):
            # Append another item.
            append_item_to_sequence(name, 'item1', repo.event_player, max_size=1)


class TestCassandraSequence(WithCassandraActiveRecordStrategies, SequenceTestCase):
    pass


class TestSQLAlchemySequence(WithSQLAlchemyActiveRecordStrategies, SequenceTestCase):
    pass
