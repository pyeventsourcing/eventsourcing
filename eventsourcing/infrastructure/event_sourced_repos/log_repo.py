from eventsourcing.domain.model.log import Log, LogRepository
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository


class LogRepo(EventSourcedRepository, LogRepository):
    """
    Event sourced repository for the Example domain model entity.
    """
    domain_class = Log
