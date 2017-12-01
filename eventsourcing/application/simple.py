from eventsourcing.application.policies import PersistencePolicy
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemyDatastore, SQLAlchemySettings
from eventsourcing.infrastructure.sqlalchemy.factory import construct_sqlalchemy_eventstore


class SimpleApplication(object):
    def __init__(self, **kwargs):
        # Setup the event store.
        self.setup_event_store(**kwargs)

        # Construct a persistence policy.
        self.persistence_policy = PersistencePolicy(self.event_store)

        # Construct an event sourced repository.
        self.repository = EventSourcedRepository(event_store=self.event_store)

    def setup_event_store(self, setup_table=True, **kwargs):
        # Setup connection to database.
        self.datastore = SQLAlchemyDatastore(settings=SQLAlchemySettings(**kwargs))
        self.datastore.setup_connection()

        # Construct event store.
        self.event_store = construct_sqlalchemy_eventstore(self.datastore.session)

        # Setup table in database.
        if setup_table:
            self.setup_table()

    def setup_table(self):
        # Setup the database table using event store's active record class.
        self.datastore.setup_table(
            self.event_store.active_record_strategy.active_record_class
        )

    def close(self):
        # Close the persistence policy.
        self.persistence_policy.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
