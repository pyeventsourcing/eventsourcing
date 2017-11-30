from eventsourcing.example.domainmodel import AbstractExampleRepository, Example
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository


class ExampleRepository(EventSourcedRepository, AbstractExampleRepository):
    """
    Event sourced repository for the Example domain model entity.
    """
    __page_size__ = 1000

    def __init__(self, *args, **kwargs):
        super(ExampleRepository, self).__init__(
            mutator=Example._mutate, *args, **kwargs
        )
