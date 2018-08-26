from __future__ import absolute_import, division, print_function, unicode_literals

from unittest.case import TestCase
from uuid import uuid4

from eventsourcing.domain.model.collection import Collection, register_new_collection
from eventsourcing.domain.model.entity import EntityIsDiscarded
from eventsourcing.domain.model.events import assert_event_handlers_empty, subscribe, unsubscribe
from eventsourcing.exceptions import RepositoryKeyError
from eventsourcing.infrastructure.repositories.collection_repo import CollectionRepository
from eventsourcing.tests.sequenced_item_tests.base import WithEventPersistence
from eventsourcing.tests.sequenced_item_tests.test_sqlalchemy_record_manager import \
    SQLAlchemyRecordManagerTestCase


class TestCollection(TestCase):
    def setUp(self):
        assert_event_handlers_empty()
        self.published_events = []
        self.subscription = (lambda x: True, lambda x: self.published_events.append(x))
        subscribe(*self.subscription)

    def tearDown(self):
        unsubscribe(*self.subscription)
        assert_event_handlers_empty()

    def test(self):
        # Register a new collection entity.
        collection_id = 'collection1'
        collection = register_new_collection(collection_id=collection_id)

        # Check collection ID is set.
        self.assertEqual(collection.id, collection_id)

        # Declare items.
        item1 = 'item1'
        item2 = 'item2'

        # Check the collection is empty.
        self.assertNotIn(item1, collection)
        self.assertNotIn(item2, collection)
        self.assertEqual(len(collection._items), 0)

        # Check there has been one Collection.Created event.
        self.assertEqual(len(self.published_events), 1)
        last_event = self.published_events[-1]
        self.assertIsInstance(last_event, Collection.Created)
        self.assertEqual(last_event.originator_id, collection_id)

        # Add item to collection.
        collection.add_item(item1)

        # Check the collection has item1 only.
        self.assertIn(item1, collection)
        self.assertNotIn(item2, collection)
        self.assertEqual(len(collection._items), 1)

        # Check there has been one Collection.ItemAdded event.
        self.assertEqual(len(self.published_events), 2)
        last_event = self.published_events[-1]
        self.assertIsInstance(last_event, Collection.ItemAdded)
        self.assertEqual(last_event.originator_id, collection_id)
        self.assertEqual(last_event.item, item1)

        # Add another item.
        collection.add_item(item2)

        # Check the collection has item1 and item2.
        self.assertIn(item1, collection)
        self.assertIn(item2, collection)
        self.assertEqual(len(collection._items), 2)

        # Check there has been another Collection.ItemAdded event.
        self.assertEqual(len(self.published_events), 3)
        last_event = self.published_events[-1]
        self.assertIsInstance(last_event, Collection.ItemAdded)
        self.assertEqual(last_event.originator_id, collection_id)
        self.assertEqual(last_event.item, item2)

        # Remove item1 from the collection.
        collection.remove_item(item1)

        # Check the collection has item2 only.
        self.assertNotIn(item1, collection)
        self.assertIn(item2, collection)
        self.assertEqual(len(collection._items), 1)

        # Check there has been a Collection.ItemRemoved event.
        self.assertEqual(len(self.published_events), 4)
        last_event = self.published_events[-1]
        self.assertIsInstance(last_event, Collection.ItemRemoved)
        self.assertEqual(last_event.originator_id, collection_id)
        self.assertEqual(last_event.item, item1)

        # Discard the collection.
        collection.__discard__()

        # Check there has been a Collection.Discarded event.
        self.assertEqual(len(self.published_events), 5)
        last_event = self.published_events[-1]
        self.assertIsInstance(last_event, Collection.Discarded)
        self.assertEqual(last_event.originator_id, collection_id)

        self.assertRaises(EntityIsDiscarded, getattr, collection, 'items')


class TestCollectionRepo(SQLAlchemyRecordManagerTestCase, WithEventPersistence):
    def test(self):
        repo = CollectionRepository(event_store=self.entity_event_store)

        # Check unknown collections are not found in the repo.
        with self.assertRaises(RepositoryKeyError):
            _ = repo[uuid4()]

        # Register a new collection.
        collection_id = register_new_collection().id

        # Check the collection is in the repo.
        collection = repo[collection_id]
        self.assertIsInstance(collection, Collection)
        self.assertEqual(collection.id, collection_id)
        # Check the collection has zero items.
        self.assertEqual(len(collection.items), 0)

        # Add item.
        item1 = 'item1'
        collection.add_item(item1)

        # Check the collection is in the repo.
        collection = repo[collection_id]
        self.assertIsInstance(collection, Collection)
        self.assertEqual(collection.id, collection_id)
        # Check the collection has one item.
        self.assertEqual(len(collection.items), 1)

        # Remove item.
        collection.remove_item(item1)

        # Check the collection is in the repo.
        collection = repo[collection_id]
        self.assertIsInstance(collection, Collection)
        self.assertEqual(collection.id, collection_id)
        # Check the collection has zero items.
        self.assertEqual(len(collection.items), 0)

        # Discard the collection.
        collection.__discard__()

        # Check the collection is not in the repo.
        with self.assertRaises(RepositoryKeyError):
            _ = repo[collection.id]
