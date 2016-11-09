from eventsourcing.domain.model.notification_log import NotificationLog, NotificationLogRepository
from eventsourcing.infrastructure.event_sourced_repo import EventSourcedRepository


class NotificationLogRepo(EventSourcedRepository, NotificationLogRepository):
    """
    Event sourced repository for the Example domain model entity.
    """
    domain_class = NotificationLog
