from eventsourcing.application.main_cassandra import EventSourcingWithCassandra
from eventsourcing.domain.model.example import register_new_example
from eventsourcing.infrastructure.event_sourced_repos.example_repo import ExampleRepository


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

