from eventsourcing.domain.model.log import Log, LogRepository, start_new_log
from eventsourcing.exceptions import RepositoryKeyError
from eventsourcing.infrastructure.event_sourced_repo import EventSourcedRepository


class LogRepo(EventSourcedRepository, LogRepository):
    """
    Event sourced repository for the Example domain model entity.
    """
    domain_class = Log

    def get_or_create(self, log_name, bucket_size):
        """
        Gets or creates a log.

        :rtype: Log
        """
        try:
            return self[log_name]
        except RepositoryKeyError:
            return start_new_log(log_name, bucket_size=bucket_size)
