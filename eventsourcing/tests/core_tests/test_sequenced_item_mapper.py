from time import time
from unittest.case import TestCase

import datetime

from decimal import Decimal

from eventsourcing.domain.model.events import VersionedEntityEvent, TimestampedEntityEvent, \
    topic_from_domain_class, DomainEvent
from eventsourcing.infrastructure.transcoding import SequencedItemMapper, SequencedItem


class Event1(VersionedEntityEvent):
    pass


class Event2(TimestampedEntityEvent):
    pass


class Event3(DomainEvent):
    pass


class TestSequencedItemMapper(TestCase):

    def test_with_versioned_entity_event(self):
        # Setup the mapper, and create an event.
        mapper = SequencedItemMapper(position_attr_name='entity_version')
        event1 = Event1(entity_id='entity1', entity_version=101)

        # Check to_sequenced_item() method results in a sequenced item.
        sequenced_item = mapper.to_sequenced_item(event1)
        self.assertIsInstance(sequenced_item, SequencedItem)
        self.assertEqual(sequenced_item.position, 101)
        self.assertEqual(sequenced_item.sequence_id, 'entity1')
        self.assertEqual(sequenced_item.topic, topic_from_domain_class(Event1))
        self.assertTrue(sequenced_item.data)

        # Use the returned values to create a new sequenced item.
        sequenced_item_copy = SequencedItem(
            sequence_id=sequenced_item.sequence_id,
            position=sequenced_item.position,
            topic=sequenced_item.topic,
            data=sequenced_item.data,
        )

        # Check from_sequenced_item() returns an event.
        domain_event = mapper.from_sequenced_item(sequenced_item_copy)
        self.assertIsInstance(domain_event, Event1)
        self.assertEqual(domain_event.entity_id, event1.entity_id)
        self.assertEqual(domain_event.entity_version, event1.entity_version)

    def test_with_timestamped_entity_event(self):
        # Setup the mapper, and create an event.
        mapper = SequencedItemMapper(position_attr_name='timestamp')
        before = time()
        event2 = Event2(entity_id='entity2')
        after = time()

        # Check to_sequenced_item() method results in a sequenced item.
        sequenced_item = mapper.to_sequenced_item(event2)
        self.assertIsInstance(sequenced_item, SequencedItem)
        self.assertGreater(sequenced_item.position, before)
        self.assertLess(sequenced_item.position, after)
        self.assertEqual(sequenced_item.sequence_id, 'entity2')
        self.assertEqual(sequenced_item.topic, topic_from_domain_class(Event2))
        self.assertTrue(sequenced_item.data)

        # Use the returned values to create a new sequenced item.
        sequenced_item_copy = SequencedItem(
            sequence_id=sequenced_item.sequence_id,
            position=sequenced_item.position,
            topic=sequenced_item.topic,
            data=sequenced_item.data,
        )

        # Check from_sequenced_item() returns an event.
        domain_event = mapper.from_sequenced_item(sequenced_item_copy)
        self.assertIsInstance(domain_event, Event2)
        self.assertEqual(domain_event.entity_id, event2.entity_id)
        self.assertEqual(domain_event.timestamp, event2.timestamp)

    def test_with_different_types_of_event_attributes(self):
        # Setup the mapper, and create an event.
        mapper = SequencedItemMapper(position_attr_name='a')

        # Create an event with dates and datetimes.
        event3 = Event3(
            entity_id='entity3',
            entity_version=303,
            a=datetime.datetime(2017, 3, 22, 9, 12, 14),
            b=datetime.date(2017, 3, 22)
        )

        # Check to_sequenced_item() method results in a sequenced item.
        sequenced_item = mapper.to_sequenced_item(event3)

        # Use the returned values to create a new sequenced item.
        sequenced_item_copy = SequencedItem(
            sequence_id=sequenced_item.sequence_id,
            position=sequenced_item.position,
            topic=sequenced_item.topic,
            data=sequenced_item.data,
        )

        # Check from_sequenced_item() returns an event.
        domain_event = mapper.from_sequenced_item(sequenced_item_copy)
        self.assertIsInstance(domain_event, Event3)
        self.assertEqual(domain_event.entity_id, event3.entity_id)
        self.assertEqual(domain_event.a, event3.a)
        self.assertEqual(domain_event.b, event3.b)

    def test_errors(self):
        # Setup the mapper, and create an event.
        mapper = SequencedItemMapper(position_attr_name='a')

        # Create an event with dates and datetimes.
        event3 = Event3(
            entity_id='entity3',
            entity_version=303,
            a=Decimal(1.0),
        )

        # Check to_sequenced_item() method results in a sequenced item.
        with self.assertRaises(TypeError):
            mapper.to_sequenced_item(event3)
