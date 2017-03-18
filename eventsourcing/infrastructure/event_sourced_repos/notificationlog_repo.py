from eventsourcing.domain.model.notificationlog import NotificationLog, NotificationLogRepository
from eventsourcing.infrastructure.oldevent_sourced_repo import EventSourcedRepository


class NotificationLogRepo(EventSourcedRepository, NotificationLogRepository):
    """
    Event sourced repository for the Example domain model entity.
    """
    domain_class = NotificationLog
