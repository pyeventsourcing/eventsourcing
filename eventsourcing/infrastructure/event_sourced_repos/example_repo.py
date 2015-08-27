from eventsourcing.domain.model.example import example_mutator, Repository
from eventsourcing.infrastructure.event_sourced_repo import EventSourcedRepository


class ExampleRepository(EventSourcedRepository, Repository):

    def get_mutator(self):
        return example_mutator
