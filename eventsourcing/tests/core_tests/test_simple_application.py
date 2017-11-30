import uuid

from eventsourcing.application.simple import SimpleApplication
from eventsourcing.domain.model.events import assert_event_handlers_empty
from eventsourcing.infrastructure.sqlalchemy.factory import construct_sqlalchemy_eventstore
from eventsourcing.tests.core_tests.test_aggregate_root import ExampleAggregateRoot
from eventsourcing.tests.datastore_tests.test_sqlalchemy import SQLAlchemyDatastoreTestCase
from eventsourcing.utils.topic import get_topic


class TestSimpleApplication(SQLAlchemyDatastoreTestCase):
    def setUp(self):
        # Setup application and database.
        self.datastore.setup_connection()
        event_store = construct_sqlalchemy_eventstore(self.datastore.session)
        self.datastore.setup_table(event_store.active_record_strategy.active_record_class)
        self.application = SimpleApplication(event_store)

    def tearDown(self):
        # Check the close() method leaves everything unsubscribed.
        self.application.close()
        assert_event_handlers_empty()

    def test(self):
        # Construct a repository.
        repository = self.application.construct_repository(ExampleAggregateRoot)

        # Save a new aggregate.
        event = ExampleAggregateRoot.Created(
            originator_id=uuid.uuid4(),
            originator_topic=get_topic(ExampleAggregateRoot)
        )
        aggregate = event.mutate()
        aggregate.publish(event)
        aggregate.save()

        # Check the application's persistence policy is effective.
        self.assertTrue(aggregate.id in repository)
