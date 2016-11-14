import json
from abc import ABCMeta, abstractmethod

import requests
import six

from eventsourcing.domain.model.log import LogRepository
from eventsourcing.domain.model.notification_log import NotificationLog
from eventsourcing.domain.model.sequence import SequenceRepository
from eventsourcing.domain.services.eventstore import AbstractEventStore
from eventsourcing.domain.services.notification_log import NotificationLogReader


class AbstractNotificationFeed(six.with_metaclass(ABCMeta)):
    @abstractmethod
    def get_doc(self, doc_id):
        """Returns feed doc, for given doc ID."""
        return {}


class AbstractNotificationFeedReader(six.with_metaclass(ABCMeta)):
    def __init__(self, feed):
        assert isinstance(feed, AbstractNotificationFeed)
        self.feed = feed

    @abstractmethod
    def get_items(self, last_item_num=None):
        """Returns all items in feed, optionally after given last item num."""
        return []


class NotificationFeed(AbstractNotificationFeed):
    """
    Provides linked sections from the log.
    """
    def __init__(self, notification_log, sequence_repo, log_repo, event_store, doc_size):
        assert isinstance(notification_log, NotificationLog), notification_log
        assert isinstance(sequence_repo, SequenceRepository), sequence_repo
        assert isinstance(log_repo, LogRepository), log_repo
        assert isinstance(event_store, AbstractEventStore), event_store
        assert isinstance(doc_size, six.integer_types), doc_size
        if notification_log.sequence_size % doc_size:
            raise ValueError("Sequence size {} not divisible by document size {}.".format(
                notification_log.sequence_size, doc_size
            ))
        self.notification_log = notification_log
        self.sequence_repo = sequence_repo
        self.log_repo = log_repo
        self.event_store = event_store
        self.doc_size = doc_size
        self.last_last_item = None
        self.last_slice_start = None
        self.last_slice_stop = None

    def get_doc(self, doc_id):
        items = self._get_items(doc_id=doc_id)
        if doc_id == 'current':
            doc_id = '{},{}'.format(self.last_slice_start + 1, self.last_slice_stop)
        doc = {'id': doc_id, 'items': items}
        if self.last_slice_start:
            first_item_number = self.last_slice_start + 1 - self.doc_size
            last_item_number = self.last_slice_stop - self.doc_size
            doc['previous'] = '{},{}'.format(first_item_number, last_item_number)
        if self.last_slice_stop < self.last_last_item:
            first_item_number = self.last_slice_start + 1 + self.doc_size
            last_item_number = self.last_slice_stop + self.doc_size
            doc['next'] = '{},{}'.format(first_item_number, last_item_number)
        return doc

    def _get_items(self, doc_id):
        reader = NotificationLogReader(
            notification_log=self.notification_log,
            sequence_repo=self.sequence_repo,
            log_repo=self.log_repo,
            event_store=self.event_store,
        )

        log_length = len(reader)
        if doc_id == 'current':
            slice_start = (log_length // self.doc_size) * self.doc_size
            slice_stop = slice_start + self.doc_size
        else:
            try:
                first_item_number, last_item_number = doc_id.split(',')
            except ValueError as e:
                raise ValueError("{}: {}".format(doc_id, e))
            slice_start = int(first_item_number) - 1
            slice_stop = int(last_item_number)
            if slice_start % self.doc_size:
                raise ValueError("Document ID {} not aligned with document size {}.".format(
                    doc_id, self.doc_size
                ))
            if slice_stop - slice_start != self.doc_size:
                raise ValueError("Document ID {} does not match document size {}.".format(
                    doc_id, self.doc_size
                ))
        self.last_last_item = log_length
        self.last_slice_start = slice_start
        self.last_slice_stop = slice_stop
        return reader[slice_start:slice_stop]


class NotificationFeedReader(AbstractNotificationFeedReader):

    def get_items(self, last_item_num=None):
        # Validate the last item number.
        if last_item_num is not None:
            if last_item_num < 1:
                raise ValueError("Item number {} must be >= 1.".format(last_item_num))

        # Get current doc.
        doc_id = 'current'
        doc = self.feed.get_doc(doc_id)

        # Follow previous links.
        while 'previous' in doc:

            # Break if we can go forward from here.
            if last_item_num is not None:
                if int(doc['id'].split(',')[0]) <= last_item_num:
                    break

            # Get the previous document.
            doc_id = doc['previous']
            doc = self.feed.get_doc(doc_id)

        # Yield items in first doc, optionally after last item number.
        items = doc['items']
        if last_item_num is not None:
            doc_first_item_number = int(doc['id'].split(',')[0])
            from_index = last_item_num - doc_first_item_number + 1
            items = items[from_index:]

        for item in items:
            yield item

        # Follow next links.
        while 'next' in doc:
            doc_id = doc['next']
            doc = self.feed.get_doc(doc_id)

            # Yield all items in all subsequent docs.
            for item in doc['items']:
                yield item


class NotificationFeedClient(AbstractNotificationFeed):
    def __init__(self, base_url, log_name):
        self.base_url = base_url
        self.log_name = log_name

    def get_doc(self, doc_id):
        # Make doc url from doc_id
        doc_url = self.base_url + self.log_name + '/' + doc_id + '/'

        # Get feed resource representation.
        feed_str = requests.get(doc_url).content
        if isinstance(feed_str, type(b'')):
            feed_str = feed_str.decode('utf8')

        # Deserialize representation of feed resource.
        return json.loads(feed_str)


# def atom_xml_from_feed_doc(doc, base_url, log_name):
#     # Start building an atom document.
#     feed_title = Title(text='Notification log {} {}'.format(log_name, doc['id']))
#     feed_id = Id(text=make_doc_url(doc['id'], base_url))
#
#     # Add entries.
#     entries = []
#     for item in doc['items']:
#         entry = Entry(
#             title=Title(item),
#             id=Id(item)
#         )
#         entries.append(entry)
#
#     # Add previous and next links.
#     links = []
#     if 'previous' in doc:
#         href = make_doc_url(doc['previous'], base_url)
#         link = Link(href=href, rel='previous')
#         links.append(link)
#     if 'next' in doc:
#         href = make_doc_url(doc['next'], base_url)
#         link = Link(href=href, rel='next')
#         links.append(link)
#
#     # Return atom string.
#     atom_feed = Feed(entry=entries, link=links, title=feed_title, id=feed_id)
#     atom_xml = str(atom_feed)
#     return atom_xml


# def feed_doc_from_atom_xml(xml_str, doc_url):
#     xml_str = xml_str.decode('utf8')
#     try:
#         atom_feed = parse(xml_str, Feed)
#     except ParseError as e:
#         raise ValueError("Couldn't parse doc: {}: {}".format(e, xml_str))
#
#     assert isinstance(atom_feed, Feed)
#
#     try:
#         feed_id = atom_feed.id.text
#     except AttributeError as e:
#         raise AttributeError("Atom doc has no ID, from: {}: {}".format(doc_url, e))
#     doc_id = split_href(feed_id)
#     items = [i.id.text for i in atom_feed.entry]
#     doc = {'id': doc_id, 'items': items}
#     for link in atom_feed.link:
#         if link.rel == 'previous':
#             doc['previous'] = split_href(link.href)
#         elif link.rel == 'next':
#             doc['next'] = split_href(link.href)
#     return doc


# def make_doc_url(doc_id, base_url):
#     return base_url.strip('/') + '/' + doc_id


# def split_href(href):
#     return href.strip('/').split('/')[-1]
