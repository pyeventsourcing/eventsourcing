from abc import ABCMeta, abstractmethod
from threading import Thread

import six

from eventsourcing.infrastructure.stored_events.transcoders import serialize_domain_event, deserialize_domain_event


class StoredEventRepository(six.with_metaclass(ABCMeta)):

    serialize_without_json = False
    serialize_with_uuid1 = False

    def __init__(self, json_encoder_cls=None, json_decoder_cls=None):
        self.json_encoder_cls = json_encoder_cls
        self.json_decoder_cls = json_decoder_cls

    @abstractmethod
    def append(self, stored_event):
        """Saves given stored event in this repository.
        :param stored_event:
        """

    @abstractmethod
    def get_entity_events(self, stored_entity_id, after=None, until=None, limit=None, query_asc=False):
        """Returns all events for given entity ID in chronological order. Limit is max 10000.
        :param until:
        :param after:
        :param stored_entity_id:
        :rtype: list
        """

    def iterate_entity_events(self, stored_entity_id, after=None, until=None, limit=None, page_size=None):
        """Returns all events for given entity ID in chronological by paging through the stored events.
        :param until:
        :param after:
        :param stored_entity_id:
        :rtype: list
        """
        return self.iterator_class(
            repo=self,
            stored_entity_id=stored_entity_id,
            after=after,
            until=until,
            limit=limit,
            page_size=page_size,
        )

    @property
    def iterator_class(self):
        return SimpleStoredEventIterator

    def get_most_recent_event(self, stored_entity_id, until=None):
        """Returns last event for given entity ID.

        :param stored_entity_id:
        :rtype: DomainEvent, NoneType
        """
        events = self.get_most_recent_events(stored_entity_id, until=until, limit=1)
        events = list(events)
        if len(events) == 1:
            return events[0]
        elif len(events) == 0:
            return None
        else:
            raise Exception("Shouldn't have more than one object: {}".format(events))

    def get_most_recent_events(self, stored_entity_id, until=None, limit=None):
        return self.get_entity_events(stored_entity_id, until=until, limit=limit)

    def serialize(self, domain_event):
        """Returns a stored event from a domain event.
        :type domain_event: object
        :param domain_event:
        """
        return serialize_domain_event(
            domain_event,
            json_encoder_cls=self.json_encoder_cls,
            without_json=self.serialize_without_json,
            with_uuid1=self.serialize_with_uuid1
        )

    def deserialize(self, stored_event):
        """Returns a domain event from a stored event.
        :type stored_event: object
        """
        return deserialize_domain_event(
            stored_event,
            json_decoder_cls=self.json_decoder_cls,
            without_json=self.serialize_without_json
        )

    @staticmethod
    def map(func, iterable):
        return six.moves.map(func, iterable)


class StoredEventIterator(six.with_metaclass(ABCMeta)):

    DEFAULT_PAGE_SIZE = 1000

    def __init__(self, repo, stored_entity_id, page_size=None, after=None, until=None, limit=None):
        assert isinstance(repo, StoredEventRepository)
        assert isinstance(stored_entity_id, six.string_types)
        assert isinstance(page_size, (six.integer_types, type(None)))
        assert isinstance(limit, (six.integer_types, type(None)))
        self.repo = repo
        self.stored_entity_id = stored_entity_id
        self.page_size = page_size or self.DEFAULT_PAGE_SIZE
        self.after = after
        self.until = until
        self.limit = limit
        self.page_counter = 0
        self.all_event_counter = 0

    def inc_page_counter(self):
        """
        Increments the page counter.

        Each query result as a page, even if there are no items in the page. This really counts queries.
         - it is easy to divide the number of events by the page size if the "correct" answer is required
         - there will be a difference in the counts when the number of events can be exactly divided by the page
           size, because there is no way to know in advance that a full page is also the last page.
        """
        self.page_counter += 1

    def inc_all_event_counter(self):
        self.all_event_counter += 1

    @abstractmethod
    def __iter__(self):
        pass


class SimpleStoredEventIterator(StoredEventIterator):

    def __iter__(self):
        # Get pages of events until we hit the last page.
        while True:
            # Get next page of events.
            stored_events = self.repo.get_entity_events(self.stored_entity_id,
                                                        after=self.after,
                                                        until=self.until,
                                                        limit=self.page_size,
                                                        query_asc=True
                                                        )
            # Count the page.
            self.inc_page_counter()

            # Start counting events in this page.
            in_page_event_counter = 0

            # Yield each stored event, so long as we aren't over the limit.
            for stored_event in stored_events:

                # Stop if we're over the limit.
                if self.limit and self.all_event_counter >= self.limit:
                    raise StopIteration

                # Count each event.
                self.inc_all_event_counter()
                in_page_event_counter += 1

                # Yield the event.
                yield stored_event

                # Update loop variables.
                self.after = stored_event.event_id

            # Decide if this is the last page.
            is_last_page = in_page_event_counter != self.page_size

            # If that was the last page, then stop iterating.
            if is_last_page:
                raise StopIteration


class ThreadedStoredEventIterator(StoredEventIterator):

    def __iter__(self):
        # Start a thread to get a page of events.
        thread = self.start_thread()

        # Get pages of stored events, until the page isn't full.
        while True:
            # Wait for the next page of events.
            thread.join()

            # Count the page.
            self.inc_page_counter()

            # Get the stored events from the thread.
            stored_events = thread.stored_events

            # Count the number of stored events in this page.
            num_stored_events = len(stored_events)

            # Decide if this is the last page.
            is_last_page = num_stored_events != self.page_size

            if not is_last_page:
                # Update loop variables.
                self.after = stored_events[-1].event_id

                # Start the next thread.
                thread = self.start_thread()

            # Yield each stored event.
            for stored_event in stored_events:

                # Stop if we're over the limit.
                if self.limit and self.all_event_counter >= self.limit:
                    raise StopIteration

                # Count each event.
                self.inc_all_event_counter()

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
            limit=self.limit,
            query_asc=True
        )
        thread.start()
        return thread


class GetEntityEventsThread(Thread):

    def __init__(self, repo, stored_entity_id, after=None, until=None, limit=None, query_asc=False, *args, **kwargs):
        super(GetEntityEventsThread, self).__init__(*args, **kwargs)
        self.repo = repo
        self.stored_entity_id = stored_entity_id
        self.after = after
        self.until = until
        self.limit = limit
        self.query_asc = query_asc
        self.stored_events = None

    def run(self):
        self.stored_events = list(self.repo.get_entity_events(
            stored_entity_id=self.stored_entity_id,
            after=self.after,
            until=self.until,
            limit=self.limit,
            query_asc=self.query_asc
        ))
