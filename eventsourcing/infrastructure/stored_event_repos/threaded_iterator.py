# coding=utf-8
from threading import Thread

from eventsourcing.domain.services.eventstore import AbstractStoredEventRepository, StoredEventIterator


class ThreadedStoredEventIterator(StoredEventIterator):
    def __iter__(self):
        # Start a thread to get a page of events.
        thread = self.start_thread()

        # Get pages of stored events, until the page isn't full.
        while True:
            # Wait for the next page of events.
            thread.join(timeout=30)

            # Count the page.
            self._inc_page_counter()

            # Get the stored events from the thread.
            stored_events = thread.stored_events

            # Count the number of stored events in this page.
            num_stored_events = len(stored_events)

            # Decide if this is the last page.
            is_last_page = num_stored_events != self.page_size

            if not is_last_page:
                # Update loop variables.
                position = stored_events[-1]
                self._update_position(position)

                # Start the next thread.
                thread = self.start_thread()

            # Yield each stored event.
            for stored_event in stored_events:

                # Stop if we're over the limit.
                if self.limit and self.all_event_counter >= self.limit:
                    raise StopIteration

                # Count each event.
                self._inc_all_event_counter()

                # Yield the event.
                yield stored_event

            # If that was the last page, then stop iterating.
            if is_last_page:
                raise StopIteration

    def start_thread(self):
        thread = GetEntityEventsThread(
            repo=self.repo,
            stored_entity_id=self.stored_entity_id,
            after=self.after,
            until=self.until,
            page_size=self.page_size,
            is_ascending=self.is_ascending
        )
        thread.start()
        return thread


class GetEntityEventsThread(Thread):
    def __init__(self, repo, stored_entity_id, after=None, until=None, page_size=None, is_ascending=True, *args,
                 **kwargs):
        super(GetEntityEventsThread, self).__init__(*args, **kwargs)
        assert isinstance(repo, AbstractStoredEventRepository)
        self.repo = repo
        self.stored_entity_id = stored_entity_id
        self.after = after
        self.until = until
        self.page_size = page_size
        self.is_ascending = is_ascending
        self.stored_events = None

    def run(self):
        self.stored_events = list(self.repo.get_entity_events(
            stored_entity_id=self.stored_entity_id,
            after=self.after,
            until=self.until,
            limit=self.page_size,
            query_ascending=self.is_ascending,
            results_ascending=self.is_ascending,
        ))
