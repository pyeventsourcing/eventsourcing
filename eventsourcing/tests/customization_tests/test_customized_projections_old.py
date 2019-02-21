from functools import reduce

from eventsourcing.tests.example_application_tests.base import WithExampleApplication
from eventsourcing.tests.sequenced_item_tests.test_sqlalchemy_record_manager import \
    SQLAlchemyRecordManagerTestCase






#
## Old stuff...

# This tests using all the domain events in the application to project
# something other than an entity. It's not really customization.

# Todo: Support stopping and resuming when iterating over all events.

class TestGetAllEventFromSQLAlchemy(SQLAlchemyRecordManagerTestCase, WithExampleApplication):
    drop_tables = True

    def test(self):
        with self.construct_application() as app:
            # Create three domain entities.
            entity1 = app.create_new_example('a1', 'b1')
            entity2 = app.create_new_example('a2', 'b2')
            entity3 = app.create_new_example('a3', 'b3')

            # Get all the domain events
            es = app.entity_event_store
            domain_events = es.all_domain_events()

            # Project the events into a set of entity IDs.
            def mutate(state, event):
                assert isinstance(state, set)
                state.add(event.originator_id)
                return state

            all_entity_ids = reduce(mutate, domain_events, set())

            # Check we got all the entity IDs.
            self.assertEqual(all_entity_ids, {entity1.id, entity2.id, entity3.id})

            # Todo: With integer sequenced items, to avoid keeping track of
            # a set of IDs, it would be possible to filter on position==0,
            # and either add that to the database query or put that in a
            # generator that yields all IDs of items with position==0 (rather
            # than yielding items that are not in a set, or keeping adding to
            # a set the same ID once for each version).
