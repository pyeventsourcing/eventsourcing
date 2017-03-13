from eventsourcing.application.base import EventSourcedApplication, NewEventSourcedApplication
from eventsourcing.example.domain_model import register_new_example
from eventsourcing.example.infrastructure import ExampleRepo
from eventsourcing.infrastructure.snapshotting import EventSourcedSnapshotStrategy, NewEventSourcedSnapshotStrategy


class ExampleApplication(EventSourcedApplication):
    """
    Abstract example event sourced application.

    This application has an Example repository, and a factory method to construct new Example entities.

    It doesn't have a stored event repository.
    """
    def __init__(self, **kwargs):
        super(ExampleApplication, self).__init__(**kwargs)
        self.snapshot_strategy = EventSourcedSnapshotStrategy(event_store=self.event_store)
        self.example_repo = ExampleRepo(event_store=self.event_store, snapshot_strategy=self.snapshot_strategy)

    def register_new_example(self, a, b):
        return register_new_example(a=a, b=b)


class NewExampleApplication(NewEventSourcedApplication):
    """
    Abstract example event sourced application.

    This application has an Example repository, and a factory method to construct new Example entities.

    It doesn't have a stored event repository.
    """
    def __init__(self, **kwargs):
        super(NewExampleApplication, self).__init__(**kwargs)
        self.snapshot_strategy = NewEventSourcedSnapshotStrategy(event_store=self.event_store)
        self.example_repo = ExampleRepo(event_store=self.event_store, snapshot_strategy=self.snapshot_strategy)

    def register_new_example(self, a, b):
        return register_new_example(a=a, b=b)
