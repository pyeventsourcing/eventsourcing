from eventsourcing.example.domainmodel import Example, ExampleRepository
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository


class ExampleRepo(EventSourcedRepository, ExampleRepository):
    """
    Event sourced repository for the Example domain model entity.
    """
    __page_size__ = 1000
    domain_class = Example

