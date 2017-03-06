import json
from abc import ABCMeta, abstractmethod

import requests
import six

from eventsourcing.domain.model.log import LogRepository
from eventsourcing.domain.model.notificationlog import NotificationLog
from eventsourcing.domain.model.sequence import SequenceRepository
from eventsourcing.infrastructure.eventstore import AbstractEventStore
from eventsourcing.infrastructure.notification_log import NotificationLogReader


class ArchivedLogRepository(six.with_metaclass(ABCMeta)):
    """
    Provides a series of archived log documents (linked sections from the notification log).
    """
    @abstractmethod
    def __getitem__(self, archived_log_id):
        """
        Returns archived log, for given ID.

        :rtype: ArchivedLog

        """


class ArchivedLog(object):
    def __init__(self, id, items, previous_id=None, next_id=None):
        self.id = id
        self.items = items
        self.previous_id = previous_id
        self.next_id = next_id


class ArchivedLogRepo(ArchivedLogRepository):
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

    def __getitem__(self, archived_log_id):
        # Read the length of the notification log.
        notification_log_length = len(self.reader)

        # Get sequence slice start and stop indices.
        if archived_log_id == 'current':
            slice_start = (notification_log_length // self.doc_size) * self.doc_size
            slice_stop = slice_start + self.doc_size
            archived_log_id = self.format_archived_log_id(slice_start + 1, slice_stop)
        else:
            try:
                first_item_number, last_item_number = archived_log_id.split(',')
            except ValueError as e:
                raise ValueError("Couldn't split archived log ID '{}': {}".format(archived_log_id, e))
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
        items = self.reader[slice_start:slice_stop]

        # Decide the IDs of previous and next archived logs.
        if self.last_slice_start:
            first_item_number = self.last_slice_start + 1 - self.doc_size
            last_item_number = self.last_slice_stop - self.doc_size
            previous_id = self.format_archived_log_id(first_item_number, last_item_number)
        else:
            previous_id = None
        if self.last_slice_stop < notification_log_length:
            first_item_number = self.last_slice_start + 1 + self.doc_size
            last_item_number = self.last_slice_stop + self.doc_size
            next_id = self.format_archived_log_id(first_item_number, last_item_number)
        else:
            next_id = None

        # Return archived log object.
        return ArchivedLog(
            id=archived_log_id,
            items=items,
            previous_id=previous_id,
            next_id=next_id,
        )

    @staticmethod
    def format_archived_log_id(first_item_number, last_item_number):
        return '{},{}'.format(first_item_number, last_item_number)


class ArchivedLogReader(six.with_metaclass(ABCMeta)):
    def __init__(self, archived_log_repo):
        assert isinstance(archived_log_repo, ArchivedLogRepository)
        self.archived_log_repo = archived_log_repo
        self.archived_log_count = 0

    def get_items(self, last_item_num=None):
        self.archived_log_count = 0

        # Validate the last item number.
        if last_item_num is not None:
            if last_item_num < 1:
                raise ValueError("Item number {} must be >= 1.".format(last_item_num))

        # Get current doc.
        archived_log_id = 'current'
        archived_log = self.archived_log_repo[archived_log_id]

        # Follow previous links.
        while archived_log.previous_id:

            # Break if we can go forward from here.
            if last_item_num is not None:
                if int(archived_log.id.split(',')[0]) <= last_item_num + 1:
                    break

            # Get the previous document.
            archived_log_id = archived_log.previous_id
            archived_log = self.archived_log_repo[archived_log_id]

        # Yield items in first doc, optionally after last item number.
        items = archived_log.items
        if last_item_num is not None:
            doc_first_item_number = int(archived_log.id.split(',')[0])
            from_index = last_item_num - doc_first_item_number + 1
            items = items[from_index:]

        # Yield all items in all subsequent archived logs.
        while True:

            for item in items:
                yield item
            self.archived_log_count += 1

            if archived_log.next_id:
                # Follow link to get next archived log.
                archived_log = self.archived_log_repo[archived_log.next_id]
                items = archived_log.items
            else:
                break


def deserialise_archived_log(archived_log_json):
    try:
        return ArchivedLog(**json.loads(archived_log_json))
    except ValueError as e:
        raise Exception("Couldn't deserialise archived log: {}: {}".format(e, archived_log_json))


def serialize_archived_log(archived_log):
    assert isinstance(archived_log, ArchivedLog)
    return json.dumps(archived_log.__dict__, indent=4)


class RemoteArchivedLogRepo(ArchivedLogRepository):
    def __init__(self, feeds_url, feed_name):
        self.feeds_url = feeds_url
        self.feed_name = feed_name

    def __getitem__(self, archived_log_id):
        archived_log_json = self.get_archived_log_json(archived_log_id)
        return deserialise_archived_log(archived_log_json)

    def get_archived_log_json(self, archived_log_id):
        archived_log_url = self.make_archived_log_url(archived_log_id)
        return self.get_resource(archived_log_url)

    def get_resource(self, doc_url):
        representation = requests.get(doc_url).content
        if isinstance(representation, type(b'')):
            representation = representation.decode('utf8')
        return representation

    def make_archived_log_url(self, archived_log_id):
        return '{}/{}/{}/'.format(
            self.feeds_url.strip('/'),
            self.feed_name,
            archived_log_id
        )
