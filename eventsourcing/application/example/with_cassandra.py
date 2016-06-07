from eventsourcing.application.with_cassandra import EventSourcingWithCassandra
from eventsourcing.application.example.base import ExampleApplication


class ExampleApplicationWithCassandra(EventSourcingWithCassandra, ExampleApplication):
    """
    Example event sourced application.

    This application has an Example repository, and a factory method for
    registering new examples. It inherits an event store, a persistence
    subscriber, and a stored event repository, and a database connection.
    """
    pass
