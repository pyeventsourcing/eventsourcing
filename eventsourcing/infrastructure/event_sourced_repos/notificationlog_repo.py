from eventsourcing.domain.model.notification_log import NotificationLog, NotificationLogRepository,\
    create_notification_log
from eventsourcing.exceptions import RepositoryKeyError
from eventsourcing.infrastructure.event_sourced_repo import EventSourcedRepository


class NotificationLogRepo(NotificationLogRepository, EventSourcedRepository):
    """
    Event sourced repository for the Example domain model entity.
    """
    domain_class = NotificationLog

    def get_or_create(self, log_name):
        """
        Gets or creates a log.

        :rtype: Log
        """
        try:
            return self[log_name]
        except RepositoryKeyError:
            return create_notification_log(log_name)
