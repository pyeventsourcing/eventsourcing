from uuid import uuid1

import six
from six import with_metaclass

from eventsourcing.domain.model.events import QualnameABCMeta
from eventsourcing.domain.model.log import Log, MessageLogged, make_bucket_id, next_bucket_starts, \
    previous_bucket_starts
from eventsourcing.infrastructure.event_store import EventStore
from eventsourcing.infrastructure.stored_events.transcoders import make_stored_entity_id
from eventsourcing.utils.time import timestamp_from_uuid


def get_log_reader(log, event_store):
    """
    :rtype: LogReader
    """
    return LogReader(log=log, event_store=event_store)


class LogReader(with_metaclass(QualnameABCMeta)):
    def __init__(self, log, event_store, page_size=50):
        assert isinstance(log, Log)
        self.log = log
        assert isinstance(event_store, EventStore)
        self.event_store = event_store
        assert isinstance(page_size, six.integer_types)
        self.page_size = page_size
        self.position = None

    def get_messages(self, after=None, until=None, limit=None, is_ascending=False, page_size=None):
        for event in self.get_events(after, until, limit, is_ascending, page_size):
            if isinstance(event, MessageLogged):
                self.position = event.domain_event_id
                yield event.message

    def get_events(self, after=None, until=None, limit=None, is_ascending=False, page_size=None):
        assert limit is None or limit > 0

        if after is None:
            after_timestamp = None
        else:
            after_timestamp = timestamp_from_uuid(after)
        if until is None:
            until_timestamp = None
        else:
            until_timestamp = timestamp_from_uuid(until)

        now_timestamp = timestamp_from_uuid(uuid1())
        started_on = self.log.started_on
        if is_ascending:
            # Start with the log start time, and continue until now.
            timestamp = started_on if after is None else max(after_timestamp, started_on)
        else:
            timestamp = now_timestamp if until is None else min(until_timestamp, now_timestamp)

        # Start counting events.
        count_events = 0

        while True:
            entity_id = make_bucket_id(self.log.name, timestamp, self.log.bucket_size)
            stored_entity_id = make_stored_entity_id('MessageLogged', entity_id)
            for message_logged_event in self.event_store.get_entity_events(
                    stored_entity_id=stored_entity_id,
                    after=after,
                    until=until,
                    limit=limit,
                    is_ascending=is_ascending,
                    page_size=page_size,
            ):
                yield message_logged_event

                if limit is not None:
                    count_events += 1
                    if count_events >= limit:
                        raise StopIteration

            # See if there's another bucket.
            if is_ascending:
                next_timestamp = next_bucket_starts(timestamp, self.log.bucket_size)
                if next_timestamp > (until_timestamp or now_timestamp):
                    raise StopIteration
                else:
                    timestamp = next_timestamp
            else:
                if timestamp < (after_timestamp or started_on):
                    raise StopIteration
                else:
                    timestamp = previous_bucket_starts(timestamp, self.log.bucket_size)
