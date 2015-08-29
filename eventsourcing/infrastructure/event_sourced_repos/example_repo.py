from eventsourcing.domain.model.example import Repository, Example
from eventsourcing.infrastructure.event_sourced_repo import EventSourcedRepository


class ExampleRepository(EventSourcedRepository, Repository):
    """
    Event sourced repository for the Example domain model entity.
    """
    domain_class = Example
