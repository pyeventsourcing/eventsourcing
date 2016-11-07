from eventsourcing.domain.model.sequence import Sequence, start_sequence
from eventsourcing.domain.services.sequence import append_item_to_sequence, SequenceReader
from eventsourcing.infrastructure.event_sourced_repos.sequence import SequenceRepo
from eventsourcing.tests.unit_test_cases import AppishTestCase
from eventsourcing.tests.unit_test_cases_cassandra import CassandraRepoTestCase
from eventsourcing.tests.unit_test_cases_python_objects import PythonObjectsRepoTestCase
from eventsourcing.tests.unit_test_cases_sqlalchemy import SQLAlchemyRepoTestCase


class SequenceTestCase(AppishTestCase):
    def test(self):
        repo = SequenceRepo(self.event_store)

        # Start a new sequence.
        name = 'sequence1'
        sequence = start_sequence(name)
        self.assertIsInstance(sequence, Sequence)

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
        self.assertEqual(reader[1], 'item2')
        self.assertEqual(reader[2], 'item3')

        # Check slices also work.
        self.assertEqual(reader[0:], ['item1', 'item2', 'item3'])
        self.assertEqual(reader[0:3], ['item1', 'item2', 'item3'])
        self.assertEqual(reader[0:2], ['item1', 'item2'])
        self.assertEqual(reader[0:1], ['item1'])
        self.assertEqual(reader[1:], ['item2', 'item3'])
        self.assertEqual(reader[1:3], ['item2', 'item3'])
        self.assertEqual(reader[1:2], ['item2'])
        self.assertEqual(reader[1:1], [])
        self.assertEqual(reader[2:], ['item3'])
        self.assertEqual(reader[2:3], ['item3'])
        self.assertEqual(reader[3:], [])
        self.assertEqual(reader[3:3], [])
        self.assertEqual(reader[0:300], ['item1', 'item2', 'item3'])
        self.assertEqual(reader[2:1], [])

        # Check iterator.
        for i, item in enumerate(reader):
            self.assertEqual(item, 'item{}'.format(i + 1))

        # Check len.
        self.assertEqual(len(reader), 3)

        # Check index errors.
        with self.assertRaises(IndexError):
            reader[3]

        with self.assertRaises(IndexError):
            reader[4]

        with self.assertRaises(IndexError):
            reader[-1]

        with self.assertRaises(IndexError):
            reader[-2:-1]

        with self.assertRaises(IndexError):
            reader[-1:0]

        with self.assertRaises(IndexError):
            reader[0:-1]


class TestPythonObjectsSequence(PythonObjectsRepoTestCase, SequenceTestCase):
    pass


class TestCassandraSequence(CassandraRepoTestCase, SequenceTestCase):
    pass


class TestSQLAlchemySequence(SQLAlchemyRepoTestCase, SequenceTestCase):
    pass
