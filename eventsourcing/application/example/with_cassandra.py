from eventsourcing.application.with_cassandra import EventSourcingWithCassandra
from eventsourcing.application.example.base import ExampleApplication
from eventsourcing.domain.model.example import register_new_example
from eventsourcing.infrastructure.event_sourced_repos.example_repo import ExampleRepository


class ExampleApplicationWithCassandra(EventSourcingWithCassandra, ExampleApplication):
    """
    Example event sourced application.

    This application has an Example repository, and a factory method for
    registering new examples. It inherits an event store, a persistence
    subscriber, and a stored event repository, and a database connection.
    """
    pass
