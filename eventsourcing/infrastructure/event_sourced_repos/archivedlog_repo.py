from eventsourcing.domain.model.archivedlog import ArchivedLog, ArchivedLogRepository, create_archived_log, \
    make_current_archived_log_id
from eventsourcing.exceptions import RepositoryKeyError
from eventsourcing.infrastructure.event_sourced_repo import EventSourcedRepository


class ArchivedLogRepo(EventSourcedRepository):
    """
    Event sourced repository for the Example domain model entity.
    """
    domain_class = ArchivedLog

    def get_or_create(self, log_name, log_size):
        """
        Gets or creates a log.

        :rtype: Log
        """
        try:
            return self[make_current_archived_log_id(log_name)]
        except RepositoryKeyError:
            return create_archived_log(log_name, log_size)
