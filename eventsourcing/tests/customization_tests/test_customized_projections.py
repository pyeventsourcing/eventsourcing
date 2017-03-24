from eventsourcing.tests.example_application_tests.base import WithExampleApplication
from eventsourcing.tests.sequenced_item_tests.test_sqlalchemy_active_record_strategy import \
    WithSQLAlchemyActiveRecordStrategies


class TestGetAllEventFromSQLAlchemy(WithSQLAlchemyActiveRecordStrategies, WithExampleApplication):

    def test(self):
        with self.construct_application() as app:
            domain_events = self.get_all_domain_events(app)
            self.assertEqual(len(domain_events), 0)

            app.register_new_example('a1', 'b1')
            app.register_new_example('a2', 'b2')
            app.register_new_example('a3', 'b3')

            domain_events = self.get_all_domain_events(app)
            self.assertEqual(len(domain_events), 3)

    def get_all_domain_events(self, app):
        es = app.version_entity_event_store
        active_records = es.active_record_strategy.filter()
        domain_events = []
        for r in active_records:
            i = es.active_record_strategy.from_active_record(r)
            e = es.sequenced_item_mapper.from_sequenced_item(i)
            domain_events.append(e)
        return domain_events
