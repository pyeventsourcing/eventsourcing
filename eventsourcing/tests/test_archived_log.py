from threading import Thread

from eventsourcing.infrastructure.event_sourced_repos.log_repo import LogRepo
from eventsourcing.infrastructure.event_sourced_repos.notificationlog_repo import NotificationLogRepo
from eventsourcing.infrastructure.event_sourced_repos.sequence import SequenceRepo
from eventsourcing.infrastructure.notification_log import append_item_to_notification_log
from eventsourcing.interface.archived_logs import ArchivedLogReader, ArchivedLogRepo, RemoteArchivedLogRepo, \
    serialize_archived_log
from eventsourcing.tests.stored_event_repository_tests.base_cassandra import CassandraRepoTestCase
from eventsourcing.tests.stored_event_repository_tests.base_sqlalchemy import SQLAlchemyRepoTestCase
from eventsourcing.tests.stored_event_repository_tests.base import PersistenceSubscribingTestCase
from eventsourcing.tests.unit_test_cases_python_objects import PythonObjectsRepoTestCase


class NotificationLogContext(object):

    def __init__(self, event_store):
        super(NotificationLogContext, self).__init__()
        self.event_store = event_store
        self.log_repo = LogRepo(event_store)
        self.sequence_repo = SequenceRepo(event_store)
        self.notification_log_repo = NotificationLogRepo(event_store)

    def get_or_create_notification_log(self, log_name, sequence_size):
        return self.notification_log_repo.get_or_create(
            log_name=log_name,
            sequence_size=sequence_size,
        )

    def append_notification(self, notification_log, item):
        append_item_to_notification_log(
            notification_log=notification_log,
            item=item,
            sequence_repo=self.sequence_repo,
            log_repo=self.log_repo,
            event_store=self.sequence_repo.event_store,
        )

    def create_archived_log_repo(self, notification_log, doc_size):
        return ArchivedLogRepo(
            notification_log=notification_log,
            sequence_repo=self.sequence_repo,
            log_repo=self.log_repo,
            event_store=self.event_store,
            doc_size=doc_size,
        )


class ArchivedLogTestCase(PersistenceSubscribingTestCase):

    def setUp(self):
        super(ArchivedLogTestCase, self).setUp()
        self.app = NotificationLogContext(self.event_store)

    def test_archived_log_repo(self):
        notification_log = self.app.get_or_create_notification_log('log1', sequence_size=10)

        # Create an archived log repo.
        doc_size = 5
        repo = self.app.create_archived_log_repo(notification_log, doc_size)

        # Check the archived logs.
        archived_log = repo['current']
        self.assertEqual(archived_log.id, '1,5')
        self.assertEqual(len(archived_log.items), 0)
        self.assertIsNone(archived_log.previous_id)
        self.assertIsNone(archived_log.previous_id)

        # Append items to notification log.
        self.append_notifications(notification_log, 13)

        # Check the archived logs.
        self.assert_archived_log(repo, 'current', '11,15', 3, '6,10', None)
        self.assert_archived_log(repo, '1,5', '1,5', doc_size, None, '6,10')
        self.assert_archived_log(repo, '6,10', '6,10', doc_size, '1,5', '11,15')
        self.assert_archived_log(repo, '11,15', '11,15', 3, '6,10', None)
        self.assert_archived_log(repo, '16,20', '16,20', 0, '11,15', None)
        self.assert_archived_log(repo, '21,25', '21,25', 0, '16,20', None)

        # Add some more items.
        self.append_notifications(notification_log, 13, 24)

        # Check the archived logs have been extended.
        self.assertEqual(len(repo['11,15'].items), doc_size)
        self.assertEqual(len(repo['16,20'].items), doc_size)
        self.assertEqual(len(repo['21,25'].items), 4)
        self.assertEqual(len(repo['26,30'].items), 0)

        # Check sequence size must be divisible by doc size.
        with self.assertRaises(ValueError):
            self.app.create_archived_log_repo(notification_log, doc_size=6)

        # Check the doc ID must match the doc size.
        repo = self.app.create_archived_log_repo(notification_log, doc_size)
        with self.assertRaises(ValueError):
            _ = repo['1,2']

        # Check the doc ID must be aligned to the doc size.
        repo = self.app.create_archived_log_repo(notification_log, doc_size)
        with self.assertRaises(ValueError):
            _ = repo['2,6']

    def test_archived_log_reader(self):
        # Build a notification log (fixture).
        notification_log = self.app.get_or_create_notification_log('log1', sequence_size=10)
        self.append_notifications(notification_log, 13)

        # Construct a feed object.
        archived_log_repo = self.app.create_archived_log_repo(notification_log, 5)

        # Use a feed reader to read the feed.
        reader = ArchivedLogReader(archived_log_repo)
        self.assertEqual(len(list(reader.get_items())), 13, list(reader.get_items()))

        # Add some more items to the log.
        self.append_notifications(notification_log, 13, 21)

        # Use archived log reader to generate notifications from the archived log repo.
        reader = ArchivedLogReader(archived_log_repo)
        self.assertEqual(len(list(reader.get_items())), 21)

        # Read items after last item number.
        self.assertEqual(len(list(reader.get_items(last_item_num=1))), 20)
        self.assertEqual(len(list(reader.get_items(last_item_num=2))), 19)
        self.assertEqual(len(list(reader.get_items(last_item_num=3))), 18)
        self.assertEqual(len(list(reader.get_items(last_item_num=19))), 2)
        self.assertEqual(len(list(reader.get_items(last_item_num=20))), 1)
        self.assertEqual(len(list(reader.get_items(last_item_num=21))), 0)
        self.assertEqual(len(list(reader.get_items(last_item_num=22))), 0)
        self.assertEqual(len(list(reader.get_items(last_item_num=23))), 0)

        # Check last item numbers less than 1 cause a value errors.
        with self.assertRaises(ValueError):
            list(reader.get_items(last_item_num=-1))

        with self.assertRaises(ValueError):
            list(reader.get_items(last_item_num=0))

        # Use a feed reader to read the feed with a larger doc size.
        reader = ArchivedLogReader(archived_log_repo)
        self.assertEqual(len(list(reader.get_items())), 21)

    def test_remote_archived_log_repo(self):
        log_name = 'log2'
        sequence_size = 100
        doc_size = 20
        num_notifications = 42
        notification_log = self.app.get_or_create_notification_log(log_name, sequence_size)

        # Build a notification log (fixture).
        self.append_notifications(notification_log, num_notifications)

        # Start a simple server.
        from wsgiref.util import setup_testing_defaults
        from wsgiref.simple_server import make_server

        port = 8000
        base_url = 'http://127.0.0.1:{}/notifications/'.format(port)

        def simple_app(environ, start_response):
            """Simple WSGI application, for testing purposes only."""
            setup_testing_defaults(environ)
            status = '200 OK'
            headers = [('Content-type', 'text/plain; charset=utf-8')]
            start_response(status, headers)

            # Extract log name and doc ID from path info.
            path_info = environ['PATH_INFO']
            try:
                notification_log_name, archived_log_id = path_info.strip('/').split('/')[-2:]
            except ValueError as e:
                msg = "Couldn't extract log name and doc ID from path info {}: {}".format(path_info, e)
                raise ValueError(msg)

            # Get serialized archived log.
            archived_log = self.app.create_archived_log_repo(notification_log, doc_size)[archived_log_id]
            archived_log_json = serialize_archived_log(archived_log)

            # Return a list of lines.
            return [(line + '\n').encode('utf8') for line in archived_log_json.split('\n')]

        httpd = make_server('', port, simple_app)
        print("Serving on port {}...".format(port))
        thread = Thread(target=httpd.serve_forever)
        thread.setDaemon(True)
        thread.start()
        try:
            # Use reader with client to read all items in remote feed after item 5.
            archived_log_repo = RemoteArchivedLogRepo(base_url, log_name)

            # Get all the items.
            archived_log_reader = ArchivedLogReader(archived_log_repo=archived_log_repo)
            items_from_start = list(archived_log_reader.get_items())

            # Check we got all the items.
            self.assertEqual(len(items_from_start), num_notifications)
            self.assertEqual(items_from_start[0], 'item1')
            expected_log_count = (num_notifications // doc_size) + (1 if num_notifications % doc_size else 0)
            self.assertEqual(archived_log_reader.archived_log_count, expected_log_count)

            # Get all the items from item 5.
            items_from_5 = list(archived_log_reader.get_items(last_item_num=doc_size))

            # Check we got everything after item 5.
            self.assertEqual(len(items_from_5), num_notifications - doc_size)
            self.assertEqual(items_from_5[0], 'item{}'.format(doc_size + 1))
            expected_log_count = (num_notifications // doc_size) + (1 if num_notifications % doc_size else 0) - 1
            self.assertEqual(archived_log_reader.archived_log_count, expected_log_count)

        finally:
            httpd.shutdown()
            thread.join()
            httpd.server_close()

    def assert_archived_log(self, repo, archived_log_id, expected_id, expected_len_items, expected_previous_id,
                            expected_next_id):
        archived_log = repo[archived_log_id]
        self.assertEqual(len(archived_log.items), expected_len_items)
        self.assertEqual(archived_log.id, expected_id)
        self.assertEqual(archived_log.previous_id, expected_previous_id)
        self.assertEqual(archived_log.next_id, expected_next_id)

    def append_notifications(self, notification_log, *range_args):
        for i in range(*range_args):
            item = 'item{}'.format(i + 1)
            self.app.append_notification(notification_log, item)


class TestArchivedLogWithPythonObjects(PythonObjectsRepoTestCase, ArchivedLogTestCase):
    pass


class TestArchivedLogWithCassandra(CassandraRepoTestCase, ArchivedLogTestCase):
    pass


class TestArchivedLogWithSQLAlchemy(SQLAlchemyRepoTestCase, ArchivedLogTestCase):
    pass
