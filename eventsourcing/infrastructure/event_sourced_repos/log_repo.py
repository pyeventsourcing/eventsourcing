from eventsourcing.domain.model.log import Log, LogRepository
from eventsourcing.infrastructure.event_sourced_repo import EventSourcedRepository


class LogRepo(EventSourcedRepository, LogRepository):
    """
    Event sourced repository for the Example domain model entity.
    """
    domain_class = Log
