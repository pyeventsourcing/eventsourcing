from eventsourcing.application.example.base import ExampleApplication
from eventsourcing.application.with_pythonobjects import EventSourcingWithPythonObjects


class ExampleApplicationWithPythonObjects(EventSourcingWithPythonObjects, ExampleApplication):
    """
    Example event sourced application.

    This application has an Example repository, and a factory method for
    registering new examples. It inherits an event store, a persistence
    subscriber, and a stored event repository, and a database connection.
    """
    pass
