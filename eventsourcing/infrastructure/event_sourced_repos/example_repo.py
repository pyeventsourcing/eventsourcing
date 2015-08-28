from eventsourcing.domain.model.example import Repository, Example
from eventsourcing.infrastructure.event_sourced_repo import EventSourcedRepository


class ExampleRepository(EventSourcedRepository, Repository):

    domain_class = Example
