from math import ceil
from threading import Thread
from unittest.case import TestCase
from uuid import uuid4

from eventsourcing.infrastructure.repositories.array import BigArrayRepository
from eventsourcing.interface.notificationlog import NotificationLog, NotificationLogReader, \
    RemoteNotificationLog, deserialize_section, present_section
from eventsourcing.tests.sequenced_item_tests.base import WithPersistencePolicies
from eventsourcing.tests.sequenced_item_tests.test_cassandra_active_record_strategy import \
    WithCassandraActiveRecordStrategies
from eventsourcing.tests.sequenced_item_tests.test_sqlalchemy_active_record_strategy import \
    WithSQLAlchemyActiveRecordStrategies


class ArchivedLogTestCase(WithSQLAlchemyActiveRecordStrategies, WithPersistencePolicies):
    def setUp(self):
        super(ArchivedLogTestCase, self).setUp()
        self.big_array_repo = BigArrayRepository(event_store=self.entity_event_store)

    def create_big_array(self, big_array_id=None):
        big_array_id = uuid4() if big_array_id is None else big_array_id
        big_array = self.big_array_repo[big_array_id]
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


class TestNotificationLog(ArchivedLogTestCase):
    def test_notification_log(self):
        # Build notification log.
        big_array = self.create_big_array()
        section_size = 5
        notification_log = NotificationLog(big_array, section_size=section_size)

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
            NotificationLog(big_array, section_size=6)

        # Check the section ID must match the section size.
        notification_log = NotificationLog(big_array, section_size)
        with self.assertRaises(ValueError):
            _ = notification_log['1,2']

        # Check the section ID must be aligned to the array size.
        with self.assertRaises(ValueError):
            _ = notification_log['2,6']

        # Check an section ID that can't be split by ',' results in a ValueError.
        with self.assertRaises(ValueError):
            _ = notification_log['invalid']

    def test_notification_log_reader(self):
        # Build notification log.
        big_array = self.create_big_array()
        section_size = 5
        notification_log = NotificationLog(big_array, section_size=section_size)

        # Append 13 notifications.
        self.append_notifications(big_array, 13)

        # Construct notification log reader.
        reader = NotificationLogReader(notification_log)

        # Read all notifications.
        all_notifications = list(reader)
        self.assertEqual(len(all_notifications), 13, all_notifications)

        # Check position.
        self.assertEqual(reader.position, 13)

        # Add some more items to the log.
        self.append_notifications(big_array, 13, 21)

        # Read subsequent notifications.
        subsequent_notifications_notifications = list(reader)
        self.assertEqual(len(subsequent_notifications_notifications), 8, subsequent_notifications_notifications)

        # Check position.
        self.assertEqual(reader.position, 21)

        subsequent_notifications_notifications = list(reader)
        self.assertEqual(len(subsequent_notifications_notifications), 0, subsequent_notifications_notifications)

        # Set position.
        reader.seek(13)
        subsequent_notifications_notifications = list(reader)
        self.assertEqual(len(subsequent_notifications_notifications), 8, subsequent_notifications_notifications)

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
            reader.position = -1
            list(reader)

        with self.assertRaises(ValueError):
            list(reader.seek(-1))

        # Check resuming from a saved position.
        saved_position = 5
        advance_by = 3
        reader.seek(saved_position)
        count = 0
        self.assertEqual(reader.position, saved_position)
        for _ in reader:
            count += 1
            if count > advance_by:
                break
        else:
            self.fail("for loop didn't break")
        self.assertEqual(reader.position, saved_position + advance_by)

        # Read items between particular positions.
        # - check stops at end of slice, and position tracks ok
        self.assertEqual(len(list(reader[0:1])), 1)
        self.assertEqual(reader.position, 1)

        self.assertEqual(len(list(reader[1:3])), 2)
        self.assertEqual(reader.position, 3)

        self.assertEqual(len(list(reader[2:5])), 3)
        self.assertEqual(reader.position, 5)

        self.assertEqual(len(list(reader[3:7])), 4)
        self.assertEqual(reader.position, 7)

        self.assertEqual(len(list(reader[13:20])), 7)
        self.assertEqual(reader.position, 20)

        self.assertEqual(len(list(reader[18:20])), 2)
        self.assertEqual(reader.position, 20)

        self.assertEqual(len(list(reader[19:20])), 1)
        self.assertEqual(reader.position, 20)

        self.assertEqual(len(list(reader[20:20])), 0)
        self.assertEqual(reader.position, 20)

        self.assertEqual(len(list(reader[21:20])), 0)
        self.assertEqual(reader.position, 21)


class TestRemoteArchivedLog(ArchivedLogTestCase):
    use_named_temporary_file = True

    def test_remote_notification_log(self):
        log_name = str(uuid4())
        num_notifications = 42
        big_array = self.create_big_array()
        section_size = 5

        # Build a notification log (fixture).
        self.append_notifications(big_array, num_notifications)

        # Start a simple server.
        from wsgiref.util import setup_testing_defaults
        from wsgiref.simple_server import make_server

        port = 8080
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
                notification_log_id, section_id = path_info.strip('/').split('/')[-2:]
            except ValueError as e:
                msg = "Couldn't extract log name and doc ID from path info {}: {}".format(path_info, e)
                raise ValueError(msg)

            # Get serialized section.
            section = present_section(big_array, section_id, section_size)

            # Return a list of lines.
            return [(line + '\n').encode('utf8') for line in section.split('\n')]

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
            expected_section_count = ceil(num_notifications / float(section_size))
            self.assertEqual(notification_log_reader.section_count, expected_section_count)

            # Get all the items from item 5.
            items_from_5 = list(notification_log_reader[section_size - 1:])

            # Check we got everything after item 5.
            self.assertEqual(len(items_from_5), num_notifications - section_size + 1)
            self.assertEqual(items_from_5[0], 'item{}'.format(section_size))
            expected_section_count = ceil(num_notifications / float(section_size))
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
