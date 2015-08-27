from eventsourcing.application.main import EventSourcedApplication
from eventsourcing.domain.model.example import register_new_example
from eventsourcing.infrastructure.event_sourced_repos.example_repo import ExampleRepository


class ExampleApplication(EventSourcedApplication):

    def __init__(self):
        super().__init__()
        self.example_repo = ExampleRepository(event_store=self.event_store)

    def register_new_example(self, a, b):
        return register_new_example(a=a, b=b)