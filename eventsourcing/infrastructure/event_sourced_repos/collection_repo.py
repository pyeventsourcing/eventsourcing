from eventsourcing.domain.model.collection import CollectionRepository, Collection
from eventsourcing.infrastructure.event_sourced_repo import EventSourcedRepository


class CollectionRepo(EventSourcedRepository, CollectionRepository):
    """
    Event sourced repository for the Collection domain model entity.
    """
    domain_class = Collection
