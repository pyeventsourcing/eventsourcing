# coding=utf-8
from abc import ABCMeta, abstractmethod
from threading import Thread

import six

from eventsourcing.exceptions import ConcurrencyError, EntityVersionDoesNotExist, ProgrammingError
from eventsourcing.infrastructure.stored_events.transcoders import StoredEvent
from eventsourcing.utils.time import time_from_uuid


# Todo: Maybe move the serialisation / deserialisation stuff to the event store, since that's the only user.

class StoredEventRepository(six.with_metaclass(ABCMeta)):

    def __init__(self, always_check_expected_version=False, always_write_entity_version=False):
        """
        Base class for a persistent collection of stored events.
        """
        self.always_check_expected_version = always_check_expected_version
        self.always_write_entity_version = always_write_entity_version
        if self.always_check_expected_version and not self.always_write_entity_version:
            raise ProgrammingError("If versions are checked, they must also be written.")

    def append(self, new_stored_event, new_version_number=None, max_retries=3, artificial_failure_rate=0):
        """
        Saves given stored event in this repository.
        """
        # Check the new event is a stored event instance.
        assert isinstance(new_stored_event, StoredEvent)

        # Validate the expected version.
        if self.always_check_expected_version:
            # noinspection PyTypeChecker
            self.validate_expected_version(new_stored_event, new_version_number)

        # Write the event.
        self.write_version_and_event(
            new_stored_event=new_stored_event,
            new_version_number=new_version_number,
            max_retries=max_retries,
            artificial_failure_rate=artificial_failure_rate,
        )


    def validate_expected_version(self, new_stored_event, new_version_number):
        """
        Checks the expected version exists and occurred before the new event.

        Raises a concurrency error if the expected version doesn't exist,
        or if the new event occurred before the expected version occurred.
        """
        assert isinstance(new_stored_event, StoredEvent)

        stored_entity_id = new_stored_event.stored_entity_id
        expected_version_number = self.decide_expected_version_number(new_version_number)
        if expected_version_number is not None:
            assert isinstance(expected_version_number, six.integer_types)
            try:
                entity_version = self.get_entity_version(
                    stored_entity_id=stored_entity_id,
                    version_number=expected_version_number
                )
            except EntityVersionDoesNotExist:
                raise ConcurrencyError("Expected version '{}' of stored entity '{}' not found."
                                       "".format(expected_version_number, stored_entity_id))
            else:
                if not time_from_uuid(new_stored_event.event_id) > time_from_uuid(entity_version.event_id):
                    raise ConcurrencyError("New event ID '{}' occurs before last version event ID '{}' for entity {}"
                                           "".format(new_stored_event.event_id, entity_version.event_id, stored_entity_id))

    def decide_expected_version_number(self, new_version_number):
        return new_version_number - 1 if new_version_number else None

    @abstractmethod
    def get_entity_version(self, stored_entity_id, version_number):
        """
        Returns entity version object for given entity version ID.

        :rtype: EntityVersion

        """

    @abstractmethod
    def write_version_and_event(self, new_stored_event, new_entity_version=None, max_retries=3, artificial_failure_rate=0):
        """
        Writes entity version and stored event into a database.
        """

    @abstractmethod
    def get_entity_events(self, stored_entity_id, after=None, until=None, limit=None, query_ascending=True,
                          results_ascending=True):
        """
        Returns all events for given entity ID in chronological order. Limit is max 10000.

        :rtype: list

        """

    def iterate_entity_events(self, stored_entity_id, after=None, until=None, limit=None, is_ascending=True,
                              page_size=None):
        """
        Returns all events for given entity ID by paging through the stored events.

        :rtype: list

        """
        return self.iterator_class(
            repo=self,
            stored_entity_id=stored_entity_id,
            page_size=min(page_size or limit, limit or page_size),
            after=after,
            until=until,
            limit=limit,
            is_ascending=is_ascending,
        )

    @property
    def iterator_class(self):
        return SimpleStoredEventIterator

    def get_most_recent_event(self, stored_entity_id, until=None):
        """
        Returns last event for given entity ID.

        :rtype: DomainEvent, NoneType

        """
        events = self.get_most_recent_events(stored_entity_id, until=until, limit=1)
        events = list(events)
        if len(events) == 1:
            return events[0]
        elif len(events) == 0:
            return None
        else:
            raise Exception("Shouldn't have more than one event object: {}"
                            "".format(events))

    def get_most_recent_events(self, stored_entity_id, until=None, limit=None):
        """
        Returns a stored event from a domain event.

        :rtype: list

        """
        return self.get_entity_events(
            stored_entity_id=stored_entity_id,
            until=until,
            limit=limit,
            query_ascending=False,
            results_ascending=False,
        )

    @staticmethod
    def map(func, iterable):
        return six.moves.map(func, iterable)

    @staticmethod
    def make_entity_version_id(stored_entity_id, version):
        """
        Constructs entity version ID from stored entity ID and version number.

        :rtype: str

        """
        return u"{}::version::{}".format(stored_entity_id, version)


class StoredEventIterator(six.with_metaclass(ABCMeta)):
    DEFAULT_PAGE_SIZE = 1000

    def __init__(self, repo, stored_entity_id, page_size=None, after=None, until=None, limit=None, is_ascending=True):
        assert isinstance(repo, StoredEventRepository), type(repo)
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
        self.is_ascending = is_ascending

    def _inc_page_counter(self):
        """
        Increments the page counter.

        Each query result as a page, even if there are no items in the page. This really counts queries.
         - it is easy to divide the number of events by the page size if the "correct" answer is required
         - there will be a difference in the counts when the number of events can be exactly divided by the page
           size, because there is no way to know in advance that a full page is also the last page.
        """
        self.page_counter += 1

    def _inc_all_event_counter(self):
        self.all_event_counter += 1

    def _update_position(self, stored_event):
        if stored_event is None:
            return
        assert isinstance(stored_event, StoredEvent), type(stored_event)
        if self.is_ascending:
            self.after = stored_event.event_id
        else:
            self.until = stored_event.event_id

    @abstractmethod
    def __iter__(self):
        pass


class SimpleStoredEventIterator(StoredEventIterator):
    def __iter__(self):
        """
        Yields pages of events until the last page.

       """
        while True:
            # Get next page of events.
            if self.limit is not None:
                limit = min(self.page_size, self.limit - self.all_event_counter)
            else:
                limit = self.page_size

            if limit == 0:
                raise StopIteration

            # Get the events.
            stored_events = self.repo.get_entity_events(
                stored_entity_id=self.stored_entity_id,
                after=self.after,
                until=self.until,
                limit=limit,
                query_ascending=self.is_ascending,
                results_ascending=self.is_ascending,
            )

            # Count the page.
            self._inc_page_counter()

            # Start counting events in this page.
            in_page_event_counter = 0

            # Yield each stored event, so long as we aren't over the limit.
            for stored_event in stored_events:

                # Stop if we're over the limit.
                if self.limit and self.all_event_counter >= self.limit:
                    raise StopIteration

                # Count each event.
                self._inc_all_event_counter()
                in_page_event_counter += 1

                # Yield the event.
                yield stored_event

                # Remember the position as the last event.
                self._update_position(stored_event)

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
        assert isinstance(repo, StoredEventRepository)
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
