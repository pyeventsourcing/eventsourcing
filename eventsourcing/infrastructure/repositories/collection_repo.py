from eventsourcing.domain.model.collection import AbstractCollectionRepository, Collection
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository


class CollectionRepository(EventSourcedRepository, AbstractCollectionRepository):
    """
    Event sourced repository for the Collection domain model entity.
    """
    def __init__(self, *args, **kwargs):
        super(CollectionRepository, self).__init__(
            mutator=Collection._mutate,
            *args, **kwargs,
        )
