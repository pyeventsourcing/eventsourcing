from eventsourcing.application.base import EventSourcedApplication
from eventsourcing.example.domainmodel import create_new_example
from eventsourcing.example.infrastructure import ExampleRepository
from eventsourcing.infrastructure.snapshotting import EventSourcedSnapshotStrategy


class ExampleApplication(EventSourcedApplication):
    """
    Abstract example event sourced application.

    This application has an Example repository, and a factory method to construct new Example entities.

    It doesn't have a stored event repository.
    """

    def __init__(self, **kwargs):
        super(ExampleApplication, self).__init__(**kwargs)
        if self.snapshot_store:
            self.snapshot_strategy = EventSourcedSnapshotStrategy(
                event_store=self.snapshot_store,
            )
        else:
            self.snapshot_strategy = None
        self.example_repository = ExampleRepository(
            event_store=self.integer_sequenced_event_store,
            snapshot_strategy=self.snapshot_strategy,
        )

    def create_new_example(self, foo='', a='', b=''):
        return create_new_example(foo=foo, a=a, b=b)
