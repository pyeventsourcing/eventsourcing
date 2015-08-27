import unittest
import uuid
from eventsourcing.domain.model.events import publish

from eventsourcing.infrastructure.event_source_repo import EventSourcedRepository
from eventsourcing.infrastructure.event_store import EventStore
from eventsourcing.infrastructure.stored_events import InMemoryStoredEventRepository
from eventsourcingtests.test_domain_events import Example
from eventsourcingtests.test_event_player import example_mutator


class ExampleRepository(EventSourcedRepository):

    @property
    def mutator(self, entity, event):
        return example_mutator


def register_new_example(a, b):
    entity_id = uuid.uuid4().hex
    event = Example.Event(entity_id=entity_id, a=a, b=b)
    entity = example_mutator(None, event)
    publish(event)
    return entity


class TestEventSourcedRepository(unittest.TestCase):

    def test(self):
        stored_event_repo = InMemoryStoredEventRepository()
        event_store = EventStore(stored_event_repo=stored_event_repo)
        example_repo = ExampleRepository(event_store=event_store)

        entity_id = 'entity1'
        event_store.append(Example.Event(entity_id=entity_id, a=1, b=2))

        self.assertIn(entity_id, example_repo)
        self.assertEqual(1, example_repo[entity_id].a)
        self.assertEqual(2, example_repo[entity_id].b)
