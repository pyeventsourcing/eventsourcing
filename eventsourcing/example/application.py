from eventsourcing.application.base import ApplicationWithPersistencePolicies
from eventsourcing.example.domainmodel import create_new_example
from eventsourcing.example.infrastructure import ExampleRepository
from eventsourcing.infrastructure.snapshotting import EventSourcedSnapshotStrategy


class ExampleApplication(ApplicationWithPersistencePolicies):
    """
    Example event sourced application with entity factory and repository.
    """

    def __init__(self, **kwargs):
        super(ExampleApplication, self).__init__(**kwargs)
        self.snapshot_strategy = None
        if self.snapshot_event_store:
            self.snapshot_strategy = EventSourcedSnapshotStrategy(
                event_store=self.snapshot_event_store,
            )
        assert self.entity_event_store is not None
        self.example_repository = ExampleRepository(
            event_store=self.entity_event_store,
            snapshot_strategy=self.snapshot_strategy,
        )

    def create_new_example(self, foo='', a='', b=''):
        """Entity object factory."""
        return create_new_example(foo=foo, a=a, b=b)


def construct_example_application(**kwargs):
    """Application object factory."""
    return ExampleApplication(**kwargs)


# "Global" variable for single instance of application.
_application = None


def init_example_application(**kwargs):
    """
    Constructs single global instance of application.
    
    To be called when initialising a worker process.
    """
    global _application
    if _application is not None:
        raise AssertionError("init_example_application() has already been called")
    _application = construct_example_application(**kwargs)


def get_example_application():
    """
    Returns single global instance of application.

    To be called when handling a worker request, if required.
    """
    if _application is None:
        raise AssertionError("init_example_application() must be called first")
    assert isinstance(_application, ExampleApplication)
    return _application


def close_example_application():
    """
    Shuts down single global instance of application.
    
    To be called when tearing down, perhaps between tests, in order to allow a
    subsequent call to init_example_application().
    """
    global _application
    if _application is not None:
        _application.close()
    _application = None
