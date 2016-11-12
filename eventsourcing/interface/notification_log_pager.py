from eventsourcing.domain.services.notification_log import NotificationLogReader


class NotificationLogPager(object):
    def __init__(self, notification_log, sequence_repo, log_repo, event_store, page_size):
        self.notification_log = notification_log
        self.sequence_repo = sequence_repo
        self.log_repo = log_repo
        self.event_store = event_store
        self.page_size = page_size
        if self.notification_log.sequence_size % self.page_size:
            raise ValueError("Sequence size {} is not an integer multiple of page size {}.".format(
                self.notification_log.sequence_size, self.page_size
            ))

    def get(self, page_name):
        reader = NotificationLogReader(
            self.notification_log,
            self.sequence_repo,
            self.log_repo,
            self.event_store,
        )
        if page_name == 'current':
            last_item = len(reader)
            start = (last_item // self.page_size) * self.page_size
            stop = start + self.page_size
        else:
            try:
                first, last = page_name.split(',')
            except ValueError as e:
                raise ValueError("{}: {}".format(page_name, e))
            start = int(first) - 1
            stop = int(last)
            if start % self.page_size:
                raise ValueError("Page name {} is not aligned with page size {}.".format(
                    page_name, self.page_size
                ))
            if stop - start != self.page_size:
                raise ValueError("Page name {} does not match page size {}.".format(
                    page_name, self.page_size
                ))
        return reader[start:stop]
