from threading import Thread
from unittest.case import TestCase
from uuid import uuid4

from eventsourcing.infrastructure.event_sourced_repos.array import BigArrayRepository
from eventsourcing.interface.notificationlog import LocalNotificationLog, NotificationLogReader, \
    RemoteNotificationLog, serialize_section, deserialize_section
from eventsourcing.tests.sequenced_item_tests.base import WithPersistencePolicies
from eventsourcing.tests.sequenced_item_tests.test_cassandra_active_record_strategy import \
    WithCassandraActiveRecordStrategies
from eventsourcing.tests.sequenced_item_tests.test_sqlalchemy_active_record_strategy import \
    WithSQLAlchemyActiveRecordStrategies


class ArchivedLogTestCase(WithSQLAlchemyActiveRecordStrategies, WithPersistencePolicies):
    def setUp(self):
        super(ArchivedLogTestCase, self).setUp()
        self.app = Application(self.entity_event_store)

    def create_big_array(self, big_array_id=None):
        big_array_id = uuid4() if big_array_id is None else big_array_id
        big_array = self.app.big_array_repo[big_array_id]
        return big_array

    def assert_section(self, repo, requested_id, expected_id, expected_len_items, expected_previous_id,
                       expected_next_id):
        section = repo[requested_id]
        self.assertEqual(len(list(section.items)), expected_len_items)
        self.assertEqual(section.section_id, expected_id)
        self.assertEqual(section.previous_id, expected_previous_id)
        self.assertEqual(section.next_id, expected_next_id)

    def append_notifications(self, big_array, *range_args):
        for i in range(*range_args):
            item = 'item{}'.format(i + 1)
            big_array.append(item)


class Application(object):
    def __init__(self, event_store):
        super(Application, self).__init__()
        self.event_store = event_store
        self.big_array_repo = BigArrayRepository(event_store=self.event_store)

    def append_notification(self, big_array_id, item):
        big_array = self.big_array_repo[big_array_id]
        big_array.append(item)

    def create_notification_log(self, big_array, section_size):
        return LocalNotificationLog(big_array, section_size=section_size)


class TestNotificationLog(ArchivedLogTestCase):

    def test_notification_log(self):
        # Build notification log.
        big_array = self.create_big_array()
        section_size = 5
        notification_log = self.app.create_notification_log(big_array, section_size=section_size)

        # Check the sections.
        section = notification_log['current']
        self.assertEqual(section.section_id, '1,5')
        self.assertEqual(len(list(section.items)), 0)
        self.assertIsNone(section.previous_id)
        self.assertIsNone(section.previous_id)

        # Append notifications.
        self.append_notifications(big_array, 13)

        # Check the sections.
        self.assert_section(notification_log, 'current', '11,15', 3, '6,10', None)
        self.assert_section(notification_log, '1,5', '1,5', section_size, None, '6,10')
        self.assert_section(notification_log, '6,10', '6,10', section_size, '1,5', '11,15')
        self.assert_section(notification_log, '11,15', '11,15', 3, '6,10', None)
        self.assert_section(notification_log, '16,20', '16,20', 0, '11,15', None)
        self.assert_section(notification_log, '21,25', '21,25', 0, '16,20', None)

        # Add some more notification.
        self.append_notifications(big_array, 13, 24)

        # Check the notification log has been extended.
        self.assertEqual(len(list(notification_log['11,15'].items)), section_size)
        self.assertEqual(len(list(notification_log['16,20'].items)), section_size)
        self.assertEqual(len(list(notification_log['21,25'].items)), 4)
        self.assertEqual(len(list(notification_log['26,30'].items)), 0)

        # Check array size must be divisible by section size.
        with self.assertRaises(ValueError):
            self.app.create_notification_log(big_array, section_size=6)

        # Check the section ID must match the section size.
        notification_log = self.app.create_notification_log(big_array, section_size)
        with self.assertRaises(ValueError):
            _ = notification_log['1,2']

        # Check the section ID must be aligned to the array size.
        notification_log = self.app.create_notification_log(big_array, section_size)
        with self.assertRaises(ValueError):
            _ = notification_log['2,6']

        # Check an section ID that can't be split by ',' results in a ValueError.
        with self.assertRaises(ValueError):
            _ = notification_log['invalid']

    def test_notification_log_reader(self):
        # Build notification log.
        big_array = self.create_big_array()
        section_size = 5
        notification_log = self.app.create_notification_log(big_array, section_size=section_size)

        self.append_notifications(big_array, 13)

        # Use a feed reader to read the feed.
        reader = NotificationLogReader(notification_log)
        # self.assertEqual(len(list(reader.get_items())), 13, list(reader.get_items()))

        # Add some more items to the log.
        self.append_notifications(big_array, 13, 21)

        # Use reader to get notifications from the notification log.
        reader = NotificationLogReader(notification_log)
        # self.assertEqual(len(list(reader)), 21)

        # # Read items after a particular position.
        self.assertEqual(len(list(reader[0:])), 21)
        self.assertEqual(len(list(reader[1:])), 20)
        self.assertEqual(len(list(reader[2:])), 19)
        self.assertEqual(len(list(reader[3:])), 18)
        self.assertEqual(len(list(reader[13:])), 8)
        self.assertEqual(len(list(reader[18:])), 3)
        self.assertEqual(len(list(reader[19:])), 2)
        self.assertEqual(len(list(reader[20:])), 1)
        self.assertEqual(len(list(reader[21:])), 0)

        # Check last item numbers less than 1 cause a value errors.
        with self.assertRaises(ValueError):
            list(reader.get_items(last_item_num=-1))

        with self.assertRaises(ValueError):
            list(reader.get_items(last_item_num=0))

        # Use a feed reader to read the feed with a larger doc size.
        reader = NotificationLogReader(notification_log)
        self.assertEqual(len(list(reader)), 21)


class TestRemoteArchivedLog(ArchivedLogTestCase):
    use_named_temporary_file = True

    def test_remote_notification_log(self):
        log_name = 'log2'
        section_size = 20
        num_notifications = 42
        big_array = self.create_big_array()
        section_size = 5

        # Build a notification log (fixture).
        self.append_notifications(big_array, num_notifications)

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
            notification_log = self.app.create_notification_log(big_array, section_size=section_size)
            archived_log = notification_log[archived_log_id]
            archived_log_json = serialize_section(archived_log)

            # Return a list of lines.
            return [(line + '\n').encode('utf8') for line in archived_log_json.split('\n')]

        httpd = make_server('', port, simple_app)
        print("Serving on port {}...".format(port))
        thread = Thread(target=httpd.serve_forever)
        thread.setDaemon(True)
        thread.start()
        try:
            # Use reader with client to read all items in remote feed after item 5.
            notification_log = RemoteNotificationLog(base_url, log_name)

            # Get all the items.
            notification_log_reader = NotificationLogReader(notification_log=notification_log)
            items_from_start = list(notification_log_reader.get_items())

            # Check we got all the items.
            self.assertEqual(len(items_from_start), num_notifications)
            self.assertEqual(items_from_start[0], 'item1')
            expected_section_count = (num_notifications // section_size) + (1 if num_notifications % section_size
                                                                            else 0)
            self.assertEqual(notification_log_reader.section_count, expected_section_count)

            # Get all the items from item 5.
            items_from_5 = list(notification_log_reader.get_items(last_item_num=section_size))

            # Check we got everything after item 5.
            self.assertEqual(len(items_from_5), num_notifications - section_size + 1)
            self.assertEqual(items_from_5[0], 'item{}'.format(section_size))
            expected_section_count = (num_notifications // section_size) + (1 if num_notifications % section_size
                                                                            else 0)
            self.assertEqual(notification_log_reader.section_count, expected_section_count)

        finally:
            httpd.shutdown()
            thread.join()
            httpd.server_close()


class TestNotificationLogWithCassandra(WithCassandraActiveRecordStrategies, TestNotificationLog):
    pass


class TestErrors(TestCase):
    def test_errors(self):
        with self.assertRaises(ValueError):
            deserialize_section('invalid json')
