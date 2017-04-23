from eventsourcing.application.base import EventSourcedApplication
from eventsourcing.example.domainmodel import create_new_example
from eventsourcing.example.infrastructure import ExampleRepository
from eventsourcing.infrastructure.snapshotting import EventSourcedSnapshotStrategy


class ExampleApplication(EventSourcedApplication):
    """
    Example event sourced application.

    This application has an Example repository, and a factory method to construct new Example entities.

    It doesn't have a stored event repository.
    """

    def __init__(self, **kwargs):
        super(ExampleApplication, self).__init__(**kwargs)
        self.snapshot_strategy = None
        if self.snapshot_event_store:
            self.snapshot_strategy = EventSourcedSnapshotStrategy(
                event_store=self.snapshot_event_store,
            )
        assert self.integer_sequenced_event_store is not None
        self.example_repository = ExampleRepository(
            event_store=self.integer_sequenced_event_store,
            snapshot_strategy=self.snapshot_strategy,
        )

    def create_new_example(self, foo='', a='', b=''):
        return create_new_example(foo=foo, a=a, b=b)


def construct_example_application(**kwargs):
    return ExampleApplication(**kwargs)


application = None


def init_example_application(**kwargs):
    global application
    if application is not None:
        raise AssertionError("init_example_application() has already been called")
    application = construct_example_application(**kwargs)


def get_example_application():
    if application is None:
        raise AssertionError("init_example_application() must be called first")
    assert isinstance(application, ExampleApplication)
    return application


def close_example_application():
    global application
    if application is not None:
        application.close()
    application = None
