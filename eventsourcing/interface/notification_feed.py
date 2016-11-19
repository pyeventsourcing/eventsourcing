import json
from abc import ABCMeta, abstractmethod

import requests
import six

from eventsourcing.domain.model.log import LogRepository
from eventsourcing.domain.model.notification_log import NotificationLog
from eventsourcing.domain.model.sequence import SequenceRepository
from eventsourcing.domain.services.eventstore import AbstractEventStore
from eventsourcing.domain.services.notification_log import NotificationLogReader


class ArchivedLogProvider(six.with_metaclass(ABCMeta)):
    """
    Provides a series of archived log documents (linked sections from the notification log).
    """
    @abstractmethod
    def __getitems__(self, archived_log_id):
        """Returns archived log, for given ID."""
        return {}


class AbstractNotificationFeedReader(six.with_metaclass(ABCMeta)):
    def __init__(self, archived_log_provider):
        assert isinstance(archived_log_provider, ArchivedLogProvider)
        self.archived_log_provider = archived_log_provider

    @abstractmethod
    def get_items(self, last_item_num=None):
        """Returns all items in feed, optionally after given last item num."""
        return []


class NotificationFeed(ArchivedLogProvider):
    def __init__(self, notification_log, sequence_repo, log_repo, event_store, doc_size):
        assert isinstance(notification_log, NotificationLog), notification_log
        assert isinstance(sequence_repo, SequenceRepository), sequence_repo
        assert isinstance(log_repo, LogRepository), log_repo
        assert isinstance(event_store, AbstractEventStore), event_store
        assert isinstance(doc_size, six.integer_types), doc_size
        if notification_log.sequence_size % doc_size:
            raise ValueError("Document size {} doesn't split log sequence size {} into equal sized parts.".format(
                doc_size, notification_log.sequence_size
            ))
        self.notification_log = notification_log
        self.sequence_repo = sequence_repo
        self.log_repo = log_repo
        self.event_store = event_store
        self.doc_size = doc_size
        self.last_last_item = None
        self.last_slice_start = None
        self.last_slice_stop = None
        self.reader = NotificationLogReader(
            notification_log=self.notification_log,
            sequence_repo=self.sequence_repo,
            log_repo=self.log_repo,
            event_store=self.event_store,
        )

    def __getitems__(self, archived_log_id):
        # Read the length of the log.
        log_length = len(self.reader)

        # Resolve supported archive log names to IDs.
        if archived_log_id == 'current':
            slice_start = (log_length // self.doc_size) * self.doc_size
            slice_stop = slice_start + self.doc_size
            archived_log_id = self.format_archived_log_id(slice_start + 1, slice_stop)

        # Get items in the archived log
        items = self._get_archived_log_items(archived_log_id)

        doc = {
            'id': archived_log_id,
            'items': items,
        }

        if self.last_slice_start:
            first_item_number = self.last_slice_start + 1 - self.doc_size
            last_item_number = self.last_slice_stop - self.doc_size
            doc['previous'] = self.format_archived_log_id(first_item_number, last_item_number)

        if self.last_slice_stop < log_length:
            first_item_number = self.last_slice_start + 1 + self.doc_size
            last_item_number = self.last_slice_stop + self.doc_size
            doc['next'] = self.format_archived_log_id(first_item_number, last_item_number)

        return doc

    def _get_archived_log_items(self, archived_log_id):
        try:
            first_item_number, last_item_number = archived_log_id.split(',')
        except ValueError as e:
            raise ValueError("{}: {}".format(archived_log_id, e))
        slice_start = int(first_item_number) - 1
        slice_stop = int(last_item_number)
        if slice_start % self.doc_size:
            raise ValueError("Document ID {} not aligned with document size {}.".format(
                archived_log_id, self.doc_size
            ))
        if slice_stop - slice_start != self.doc_size:
            raise ValueError("Document ID {} does not match document size {}.".format(
                archived_log_id, self.doc_size
            ))
        self.last_slice_start = slice_start
        self.last_slice_stop = slice_stop
        return self.reader[slice_start:slice_stop]

    @staticmethod
    def format_archived_log_id(first_item_number, last_item_number):
        return '{},{}'.format(first_item_number, last_item_number)


class NotificationFeedReader(AbstractNotificationFeedReader):
    def get_items(self, last_item_num=None):
        # Validate the last item number.
        if last_item_num is not None:
            if last_item_num < 1:
                raise ValueError("Item number {} must be >= 1.".format(last_item_num))

        # Get current doc.
        archived_log_id = 'current'
        archived_log = self.archived_log_provider.__getitems__(archived_log_id)

        # Follow previous links.
        while 'previous' in archived_log:

            # Break if we can go forward from here.
            if last_item_num is not None:
                if int(archived_log['id'].split(',')[0]) <= last_item_num:
                    break

            # Get the previous document.
            archived_log_id = archived_log['previous']
            archived_log = self.archived_log_provider.__getitems__(archived_log_id)

        # Yield items in first doc, optionally after last item number.
        items = archived_log['items']
        if last_item_num is not None:
            doc_first_item_number = int(archived_log['id'].split(',')[0])
            from_index = last_item_num - doc_first_item_number + 1
            items = items[from_index:]

        for item in items:
            yield item

        # Yield all items in all subsequent archived logs.
        while 'next' in archived_log:

            # Follow link to get next archived log.
            next_archived_log_id = archived_log['next']
            archived_log = self.archived_log_provider.__getitems__(next_archived_log_id)

            # Yield all items in the archived log.
            for item in archived_log['items']:
                yield item


class HTTPNotificationFeedClient(ArchivedLogProvider):
    def __init__(self, feeds_url, feed_name):
        self.feeds_url = feeds_url
        self.feed_name = feed_name

    def __getitems__(self, archived_log_id):
        # Make doc url from doc_id.
        doc_url = self.format_doc_url(archived_log_id)

        # Get feed resource representation.
        doc_content = requests.get(doc_url).content
        if isinstance(doc_content, type(b'')):
            doc_content = doc_content.decode('utf8')

        # Return deserialized JSON.
        return json.loads(doc_content)

    def format_doc_url(self, doc_id):
        return '{}/{}/{}/'.format(self.feeds_url.strip('/'), self.feed_name, doc_id)
