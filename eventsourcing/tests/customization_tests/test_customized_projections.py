from eventsourcing.tests.example_application_tests.base import WithExampleApplication
from eventsourcing.tests.sequenced_item_tests.test_sqlalchemy_active_record_strategy import \
    WithSQLAlchemyActiveRecordStrategies


class TestGetAllEventFromSQLAlchemy(WithSQLAlchemyActiveRecordStrategies, WithExampleApplication):

    def test(self):
        with self.construct_application() as app:
            es = app.version_entity_event_store
            domain_events = es.all_domain_events()
            domain_events = list(domain_events)
            self.assertEqual(len(domain_events), 0)

            app.register_new_example('a1', 'b1')
            app.register_new_example('a2', 'b2')
            app.register_new_example('a3', 'b3')

            domain_events = es.all_domain_events()
            domain_events = list(domain_events)
            self.assertEqual(len(domain_events), 3)
