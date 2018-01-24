from eventsourcing.example.application import close_example_application, get_example_application, \
    init_example_application
from eventsourcing.infrastructure.sqlalchemy.manager import SQLAlchemyRecordManager
from eventsourcing.infrastructure.sqlalchemy.records import IntegerSequencedNoIDRecord
from eventsourcing.tests.datastore_tests.test_sqlalchemy import SQLAlchemyDatastoreTestCase


class TestExampleApplicationSingleInstanceFunctions(SQLAlchemyDatastoreTestCase):
    def setUp(self):
        super(TestExampleApplicationSingleInstanceFunctions, self).setUp()
        # Setup the database.
        self.datastore.setup_connection()
        self.datastore.setup_tables()

    def tearDown(self):
        # Teardown single instance.
        close_example_application()

        # Teardown the database.
        self.datastore.drop_tables()
        self.datastore.close_connection()
        super(TestExampleApplicationSingleInstanceFunctions, self).tearDown()

    def test(self):
        self.datastore.setup_connection()
        self.datastore.setup_tables()
        record_manager = SQLAlchemyRecordManager(
            record_class=IntegerSequencedNoIDRecord,
            session=self.datastore.session,
        )

        # Can't get the single instance before it has been constructed.
        with self.assertRaises(AssertionError):
            get_example_application()

        # Construct single instance.
        init_example_application(
            entity_record_manager=record_manager
        )

        # Can't construct single instance twice.
        with self.assertRaises(AssertionError):
            init_example_application(
                entity_record_manager=record_manager
            )

        # Get the single instance.
        app1 = get_example_application()
        app2 = get_example_application()
        self.assertEqual(id(app1), id(app2))

        # Close single instance.
        close_example_application()

        # Can't get the single instance before it has been constructed.
        with self.assertRaises(AssertionError):
            get_example_application()

        # Construct single instance.
        init_example_application(
            entity_record_manager=record_manager
        )

        # Can't construct single instance twice.
        with self.assertRaises(AssertionError):
            init_example_application(
                entity_record_manager=record_manager
            )

        # Get the single instance.
        app1 = get_example_application()
        app2 = get_example_application()
        self.assertEqual(id(app1), id(app2))
