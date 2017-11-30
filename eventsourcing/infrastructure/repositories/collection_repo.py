from eventsourcing.domain.model.collection import AbstractCollectionRepository, Collection
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository


class CollectionRepository(EventSourcedRepository, AbstractCollectionRepository):
    """
    Event sourced repository for the Collection domain model entity.
    """
