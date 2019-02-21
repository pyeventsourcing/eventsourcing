from unittest import TestCase

from eventsourcing.infrastructure.sequenceditem import SequencedItem


class TestIntegerSequencedItem(TestCase):
    def test(self):
        sequence_id = 'sequence1'
        position = 0
        topic = 'topic1'
        state = '{}'
        item = SequencedItem(
            sequence_id=sequence_id,
            position=position,
            topic=topic,
            state=state,
        )
        self.assertEqual(item.sequence_id, sequence_id)
        self.assertEqual(item.position, position)
        self.assertEqual(item.topic, topic)
        self.assertEqual(item.state, state)

        with self.assertRaises(AttributeError):
            item.sequence_id = 'sequence2'


class TestTimeSequencedItem(TestCase):
    def test(self):
        sequence_id = 'sequence1'
        position = 0
        topic = 'topic1'
        state = '{}'
        item = SequencedItem(
            sequence_id=sequence_id,
            position=position,
            topic=topic,
            state=state,
        )
        self.assertEqual(item.sequence_id, sequence_id)
        self.assertEqual(item.position, position)
        self.assertEqual(item.topic, topic)
        self.assertEqual(item.state, state)

        with self.assertRaises(AttributeError):
            item.sequence_id = 'sequence2'
