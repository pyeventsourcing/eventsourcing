import time
from decimal import Decimal
from typing import Iterable, Optional

from eventsourcing.domain.model.timebucketedlog import (
    MessageLogged,
    Timebucketedlog,
    make_timebucket_id,
    next_bucket_starts,
    previous_bucket_starts,
)
from eventsourcing.infrastructure.base import AbstractEventStore


def get_timebucketedlog_reader(
    log: Timebucketedlog, event_store: AbstractEventStore
) -> "TimebucketedlogReader":
    return TimebucketedlogReader(log=log, event_store=event_store)


class TimebucketedlogReader(object):
    def __init__(
        self, log: Timebucketedlog, event_store: AbstractEventStore, page_size: int = 50
    ):
        self.log = log
        self.event_store = event_store
        self.page_size = page_size
        self.position: Optional[Decimal] = None

    def get_messages(
        self,
        gt: Optional[int] = None,
        gte: Optional[int] = None,
        lt: Optional[int] = None,
        lte: Optional[int] = None,
        limit: Optional[int] = None,
        is_ascending: bool = False,
        page_size: Optional[int] = None,
    ) -> Iterable[str]:
        events = self.get_events(
            gt=gt,
            gte=gte,
            lt=lt,
            lte=lte,
            limit=limit,
            is_ascending=is_ascending,
            page_size=page_size,
        )
        for event in events:
            if isinstance(event, MessageLogged):
                self.position = event.timestamp
                yield event.message

    def get_events(
        self,
        gt: Optional[int] = None,
        gte: Optional[int] = None,
        lt: Optional[int] = None,
        lte: Optional[int] = None,
        limit: Optional[int] = None,
        is_ascending: bool = False,
        page_size: Optional[int] = None,
    ) -> Iterable[MessageLogged]:
        assert limit is None or limit > 0

        # Identify the first time bucket.
        now = time.time()
        started_on = self.log.started_on
        absolute_latest = min(float(now), lt or now, lte or now)
        absolute_earlyist = max(float(started_on), gt or 0, gte or 0)
        if is_ascending:
            position = absolute_earlyist
        else:
            position = absolute_latest

        # Start counting events.
        count_events = 0

        while True:
            bucket_id = make_timebucket_id(
                self.log.name, position, self.log.bucket_size
            )
            for message_logged_event in self.event_store.iter_events(
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
