from eventsourcing.application.base import EventSourcingApplication
from eventsourcing.domain.model.example import register_new_example
from eventsourcing.infrastructure.event_sourced_repos.example_repo import ExampleRepo


class ExampleApplication(EventSourcingApplication):
    """
    Abstract example event sourced application.

    This application has an Example repository, and a factory method to construct new Example entities.

    It doesn't have a stored event repository.
    """
    def __init__(self, **kwargs):
        super(ExampleApplication, self).__init__(**kwargs)
        self.example_repo = ExampleRepo(self.event_store)

    def register_new_example(self, a, b):
        return register_new_example(a=a, b=b)
