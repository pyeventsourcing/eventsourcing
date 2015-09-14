from eventsourcing.application.main import EventSourcingApplication, EventSourcingWithSQLAlchemy, EventSourcingWithCassandra
from eventsourcing.domain.model.example import register_new_example
from eventsourcing.infrastructure.event_sourced_repos.example_repo import ExampleRepository


class ExampleApplicationWithSQLAlchemy(EventSourcingWithSQLAlchemy):
    """
    Example event sourced application.

    This application has an Example repository, and a factory method for
    registering new examples. It inherits an event store, a persistence
    subscriber, and a stored event repository, and a database connection.
    """
    def __init__(self, db_session=None, db_uri=None):
        """
        Args:
            db_uri: Database connection string for stored event repository.
        """
        super(ExampleApplicationWithSQLAlchemy, self).__init__(db_session=db_session, db_uri=db_uri)
        self.example_repo = ExampleRepository(event_store=self.event_store)

    def register_new_example(self, a, b):
        return register_new_example(a=a, b=b)


class ExampleApplicationWithCassandra(EventSourcingWithCassandra):
    """
    Example event sourced application.

    This application has an Example repository, and a factory method for
    registering new examples. It inherits an event store, a persistence
    subscriber, and a stored event repository, and a database connection.
    """
    def __init__(self):
        """
        Args:
            db_uri: Database connection string for stored event repository.
        """
        super(ExampleApplicationWithCassandra, self).__init__()
        self.example_repo = ExampleRepository(event_store=self.event_store)

    def register_new_example(self, a, b):
        return register_new_example(a=a, b=b)
