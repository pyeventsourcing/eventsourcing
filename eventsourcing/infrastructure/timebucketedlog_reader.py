from eventsourcing.domain.model.timebucketedlog import MessageLogged, Timebucketedlog, make_timebucket_id, \
    next_bucket_starts, previous_bucket_starts
from eventsourcing.infrastructure.eventstore import AbstractEventStore
from eventsourcing.utils.times import decimaltimestamp


def get_timebucketedlog_reader(log, event_store):
    """
    :rtype: TimebucketedlogReader
    """
    return TimebucketedlogReader(log=log, event_store=event_store)


class TimebucketedlogReader(object):
    def __init__(self, log, event_store, page_size=50):
        assert isinstance(log, Timebucketedlog)
        self.log = log
        assert isinstance(event_store, AbstractEventStore), event_store
        self.event_store = event_store
        assert isinstance(page_size, int)
        self.page_size = page_size
        self.position = None

    def get_messages(self, gt=None, gte=None, lt=None, lte=None, limit=None, is_ascending=False, page_size=None):
        events = self.get_events(gt=gt, gte=gte, lt=lt, lte=lte, limit=limit, is_ascending=is_ascending,
                                 page_size=page_size)
        for event in events:
            if isinstance(event, MessageLogged):
                self.position = event.timestamp
                yield event.message

    def get_events(self, gt=None, gte=None, lt=None, lte=None, limit=None, is_ascending=False, page_size=None):
        assert limit is None or limit > 0

        # Identify the first time bucket.
        now = decimaltimestamp()
        started_on = self.log.started_on
        absolute_latest = min(now, lt or now, lte or now)
        absolute_earlyist = max(started_on, gt or 0, gte or 0)
        if is_ascending:
            position = absolute_earlyist
        else:
            position = absolute_latest

        # Start counting events.
        count_events = 0

        while True:
            bucket_id = make_timebucket_id(self.log.name, position, self.log.bucket_size)
            for message_logged_event in self.event_store.get_domain_events(
                originator_id=bucket_id,
                gt=gt,
                gte=gte,
                lt=lt,
                lte=lte,
                limit=limit,
                is_ascending=is_ascending,
                page_size=page_size,
            ):
                yield message_logged_event

                if limit is not None:
                    count_events += 1
                    if count_events >= limit:
                        return

            # See if there's another bucket.
            if is_ascending:
                next_timestamp = next_bucket_starts(position, self.log.bucket_size)
                if next_timestamp > absolute_latest:
                    return
                else:
                    position = next_timestamp
            else:
                if position < absolute_earlyist:
                    return
                else:
                    position = previous_bucket_starts(position, self.log.bucket_size)
