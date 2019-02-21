from abc import ABC, abstractmethod
from threading import Thread

from eventsourcing.infrastructure.base import AbstractSequencedItemRecordManager


class AbstractSequencedItemIterator(ABC):
    DEFAULT_PAGE_SIZE = 1000

    def __init__(self, record_manager, sequence_id, page_size=None, gt=None, gte=None, lt=None, lte=None,
                 limit=None, is_ascending=True):
        assert isinstance(record_manager, AbstractSequencedItemRecordManager), type(record_manager)
        assert isinstance(page_size, (int, type(None)))
        assert isinstance(limit, (int, type(None)))
        self.record_manager = record_manager
        self.sequence_id = sequence_id
        self.page_size = page_size or self.DEFAULT_PAGE_SIZE
        self.gt = gt
        self.gte = gte
        self.lte = lte
        self.lt = lt
        self.limit = limit
        self.query_counter = 0
        self.page_counter = 0
        self.all_item_counter = 0
        self.is_ascending = is_ascending
        self._position = None

    def _inc_page_counter(self):
        """
        Increments the page counter.

        Each query result as a page, even if there are no items in the page. This really counts queries.
         - it is easy to divide the number of events by the page size if the "correct" answer is required
         - there will be a difference in the counts when the number of events can be exactly divided by the page
           size, because there is no way to know in advance that a full page is also the last page.
        """
        self.page_counter += 1

    def _inc_query_counter(self):
        """
        Increments the query counter.
        """
        self.query_counter += 1

    def _inc_all_event_counter(self):
        self.all_item_counter += 1

    def _update_position(self, sequenced_item):
        assert isinstance(sequenced_item, self.record_manager.sequenced_item_class), type(sequenced_item)
        self._position = getattr(sequenced_item, self.record_manager.field_names.position)

    @abstractmethod
    def __iter__(self):
        """
        Yields a continuous sequence of items.
        """


class SequencedItemIterator(AbstractSequencedItemIterator):
    def __iter__(self):
        """
        Yields a continuous sequence of items from "pages"
        of sequenced items retrieved using the record manager.
        """
        gt = self.gt
        gte = self.gte
        lt = self.lt
        lte = self.lte

        while True:
            # Get next page of events.
            if self.limit is not None:
                limit = min(self.page_size, self.limit - self.all_item_counter)
            else:
                limit = self.page_size

            if limit == 0:
                return

            # Get the events.
            if self._position is not None:
                if self.is_ascending:
                    gt = self._position
                    gte = None
                else:
                    lt = self._position
                    lte = None

            sequenced_items = self.record_manager.get_items(
                sequence_id=self.sequence_id,
                gt=gt,
                gte=gte,
                lt=lt,
                lte=lte,
                limit=limit,
                query_ascending=self.is_ascending,
                results_ascending=self.is_ascending,
            )

            self._inc_query_counter()

            # Start counting events in this page.
            page_item_counter = 0

            # Yield each stored event.
            for sequenced_item in sequenced_items:

                # Count each event.
                self._inc_all_event_counter()
                page_item_counter += 1

                # Yield the event.
                yield sequenced_item

                # Remember the position as the last event.
                self._update_position(sequenced_item)

            # If that wasn't an empty page, count the page.
            if page_item_counter:
                self._inc_page_counter()

            # If that wasn't a full page, stop iterating (there can be no more items).
            if page_item_counter != self.page_size:
                return


class ThreadedSequencedItemIterator(AbstractSequencedItemIterator):
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
                    return

                # Count each event.
                self._inc_all_event_counter()

                # Yield the event.
                yield stored_event

            # If that was the last page, then stop iterating.
            if is_last_page:
                return

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
            record_manager=self.record_manager,
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
    def __init__(self, record_manager, sequence_id, gt=None, gte=None, lt=None, lte=None, page_size=None,
                 is_ascending=True, *args, **kwargs):
        super(GetEntityEventsThread, self).__init__(*args, **kwargs)
        assert isinstance(record_manager, AbstractSequencedItemRecordManager), type(record_manager)
        self.record_manager = record_manager
        self.stored_entity_id = sequence_id
        self.gt = gt
        self.gte = gte
        self.lt = lt
        self.lte = lte
        self.page_size = page_size
        self.is_ascending = is_ascending
        self.stored_events = None

    def run(self):
        self.stored_events = list(self.record_manager.get_items(
            sequence_id=self.stored_entity_id,
            gt=self.gt,
            gte=self.gte,
            lt=self.lt,
            lte=self.lte,
            limit=self.page_size,
            query_ascending=self.is_ascending,
            results_ascending=self.is_ascending,
        ))
