from eventsourcing.domain.model.example import ExampleRepository, Example
from eventsourcing.infrastructure.event_sourced_repo import EventSourcedRepository


class ExampleRepo(EventSourcedRepository, ExampleRepository):
    """
    Event sourced repository for the Example domain model entity.
    """
    domain_class = Example
