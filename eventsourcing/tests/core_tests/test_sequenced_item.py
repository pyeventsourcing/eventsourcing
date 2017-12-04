from unittest import TestCase

from eventsourcing.infrastructure.sequenceditem import SequencedItem


class TestIntegerSequencedItem(TestCase):
    def test(self):
        sequence_id = 'sequence1'
        position = 0
        topic = 'topic1'
        data = '{}'
        hash = ''
        item = SequencedItem(
            sequence_id=sequence_id,
            position=position,
            topic=topic,
            data=data,
            hash=hash,
        )
        self.assertEqual(item.sequence_id, sequence_id)
        self.assertEqual(item.position, position)
        self.assertEqual(item.topic, topic)
        self.assertEqual(item.data, data)
        self.assertEqual(item.hash, hash)

        with self.assertRaises(AttributeError):
            item.sequence_id = 'sequence2'


class TestTimeSequencedItem(TestCase):
    def test(self):
        sequence_id = 'sequence1'
        position = 0
        topic = 'topic1'
        data = '{}'
        hash = ''
        item = SequencedItem(
            sequence_id=sequence_id,
            position=position,
            topic=topic,
            data=data,
            hash=hash,
        )
        self.assertEqual(item.sequence_id, sequence_id)
        self.assertEqual(item.position, position)
        self.assertEqual(item.topic, topic)
        self.assertEqual(item.data, data)

        with self.assertRaises(AttributeError):
            item.sequence_id = 'sequence2'
