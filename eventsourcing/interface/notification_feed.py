import feedparser
import six

from eventsourcing.domain.model.log import LogRepository
from eventsourcing.domain.model.notification_log import NotificationLog
from eventsourcing.domain.model.sequence import SequenceRepository
from eventsourcing.domain.services.eventstore import AbstractEventStore
from eventsourcing.domain.services.notification_log import NotificationLogReader
from feedgen.feed import FeedGenerator


class NotificationFeed(object):
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
        items = self.get_items(doc_id=doc_id)
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

    def get_items(self, doc_id):
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


class NotificationFeedReader(object):
    def __init__(self, feed):
        assert isinstance(feed, NotificationFeed)
        self.feed = feed

    def get_items(self, last_item_num=None):
        # Validate the last item number.
        if last_item_num is not None:
            if last_item_num < 1:
                raise ValueError("Item number {} must be >= 1.".format(last_item_num))

        # Create the feed object.
        doc_id = 'current'
        doc = self.get_doc(doc_id)
        while 'previous' in doc:

            # Break if we can go forward from here.
            if last_item_num is not None:
                if int(doc['id'].split(',')[0]) <= last_item_num:
                    break

            # Get the previous document.
            doc_id = doc['previous']
            doc = self.get_doc(doc_id)

        # Yield items in doc, optionally after last item number.
        items = doc['items']
        if last_item_num is not None:
            doc_first_item_number = int(doc['id'].split(',')[0])
            from_index = last_item_num - doc_first_item_number + 1
            items = items[from_index:]
        for item in items:
            yield item

        # Yield all items in all subsequent docs.
        while 'next' in doc:
            doc_id = doc['next']
            doc = self.get_doc(doc_id)
            for item in doc['items']:
                yield item

    def get_doc(self, doc_id):
        return self.feed.get_doc(doc_id)


class AtomNotificationFeed(NotificationFeed):

    def __init__(self, base_url, *args, **kwargs):
        super(AtomNotificationFeed, self).__init__(*args, **kwargs)
        self.base_url = base_url

    def get_doc(self, doc_id):
        doc = super(AtomNotificationFeed, self).get_doc(doc_id)

        # Start building an atom document.
        fg = FeedGenerator()

        # Add ID and title.
        fg.id(self.make_doc_url(doc['id']))
        fg.title('Notification log {} {}'.format(self.notification_log.name, doc['id']))

        # Add entries.
        for item in doc['items']:
            fe = fg.add_entry()
            fe.id(item)
            fe.title(item)
            fe.content(item)

        # Add previous and next links.
        if 'previous' in doc:
            fg.link(href=self.make_doc_url(doc['previous']), rel='previous')
        if 'next' in doc:
            fg.link(href=self.make_doc_url(doc['next']), rel='next')

        # Return atom string.
        return fg.atom_str(pretty=True)

    def make_doc_url(self, doc_id):
        return self.base_url.strip('/') + '/' + doc_id


class AtomNotificationFeedReader(NotificationFeedReader):

    def __init__(self, base_url, log_name):
        self.base_url = base_url
        self.log_name = log_name

    def get_doc(self, doc_id):
        doc_url = self.base_url + self.log_name + '/' + doc_id + '/'

        # Get resource from URL.
        doc_atom = feedparser.parse(doc_url)
        doc_id = self.split_href(doc_atom.feed.id)
        items = [self.split_href(i['id']) for i in doc_atom.entries]
        doc = {'id': doc_id, 'items': items}
        for link in doc_atom.feed.links if hasattr(doc_atom.feed, 'links') else []:
            if link.rel == 'previous':
                doc['previous'] = self.split_href(link.href)
            elif link.rel == 'next':
                doc['next'] = self.split_href(link.href)
        return doc

    def split_href(self, href):
        return href.strip('/').split('/')[-1]
