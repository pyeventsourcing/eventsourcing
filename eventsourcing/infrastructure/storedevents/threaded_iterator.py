# coding=utf-8
from threading import Thread

from eventsourcing.infrastructure.eventstore import AbstractStoredEventIterator
from eventsourcing.infrastructure.storedevents.activerecord import AbstractActiveRecordStrategy


class ThreadedSequencedItemIterator(AbstractStoredEventIterator):
    def __iter__(self):
        # Start a thread to get a page of events.
        thread = self.start_thread()

        # Get pages of stored events, until the page isn't full.
        while True:
            # Wait for the next page of events.
            thread.join(timeout=30)

            # Count the query.
            self._inc_query_counter()

            # Get the stored events from the thread.
            stored_events = thread.stored_events

            # Count the number of stored events that were retrieved.
            num_stored_events = len(stored_events)

            if num_stored_events:
                self._inc_page_counter()

            # Decide if this is the last page.
            is_last_page = (
                num_stored_events != self.page_size
            ) or (
                self.all_item_counter + num_stored_events == self.limit
            )

            if not is_last_page:
                # Update loop variables.
                position = stored_events[-1]
                self._update_position(position)

                # Start the next thread.
                thread = self.start_thread()

            # Yield each stored event.
            for stored_event in stored_events:

                # Stop if we're over the limit.
                if self.limit and self.all_item_counter >= self.limit:
                    raise StopIteration

                # Count each event.
                self._inc_all_event_counter()

                # Yield the event.
                yield stored_event

            # If that was the last page, then stop iterating.
            if is_last_page:
                raise StopIteration

    def start_thread(self):
        gt = self.gt
        gte = self.gte
        lt = self.lt
        lte = self.lte

        if self._position is not None:
            if self.is_ascending:
                gt = self._position
                gte = None
            else:
                lt = self._position
                lte = None

        thread = GetEntityEventsThread(
            active_record_strategy=self.active_record_strategy,
            sequence_id=self.sequence_id,
            gt=gt,
            gte=gte,
            lt=lt,
            lte=lte,
            page_size=self.page_size,
            is_ascending=self.is_ascending
        )
        thread.start()
        return thread


class GetEntityEventsThread(Thread):
    def __init__(self, active_record_strategy, sequence_id, gt=None, gte=None, lt=None, lte=None, page_size=None,
                 is_ascending=True, *args, **kwargs):
        super(GetEntityEventsThread, self).__init__(*args, **kwargs)
        assert isinstance(active_record_strategy, AbstractActiveRecordStrategy), type(active_record_strategy)
        self.active_record_strategy = active_record_strategy
        self.stored_entity_id = sequence_id
        self.gt = gt
        self.gte = gte
        self.lt = lt
        self.lte = lte
        self.page_size = page_size
        self.is_ascending = is_ascending
        self.stored_events = None

    def run(self):
        self.stored_events = list(self.active_record_strategy.get_items(
            sequence_id=self.stored_entity_id,
            gt=self.gt,
            gte=self.gte,
            lt=self.lt,
            lte=self.lte,
            limit=self.page_size,
            query_ascending=self.is_ascending,
            results_ascending=self.is_ascending,
        ))
