from math import ceil
from threading import Thread
from uuid import uuid4

from eventsourcing.domain.model.events import DomainEvent
from eventsourcing.infrastructure.repositories.array import BigArrayRepository
from eventsourcing.interface.notificationlog import BigArrayNotificationLog, NotificationLogReader, \
    NotificationLogView, RecordManagerNotificationLog, RemoteNotificationLog
from eventsourcing.tests.sequenced_item_tests.base import WithEventPersistence
from eventsourcing.tests.sequenced_item_tests.test_cassandra_record_manager import \
    WithCassandraRecordManagers
from eventsourcing.tests.sequenced_item_tests.test_django_record_manager import DjangoTestCase
from eventsourcing.tests.sequenced_item_tests.test_sqlalchemy_record_manager import \
    SQLAlchemyRecordManagerTestCase
from eventsourcing.utils.topic import get_topic


class NotificationLogTestCase(SQLAlchemyRecordManagerTestCase, WithEventPersistence):

    def assert_section(self, repo, requested_id, expected_id, expected_len_items, expected_previous_id,
                       expected_next_id):
        section = repo[requested_id]
        self.assertEqual(expected_len_items, len(list(section.items)))
        self.assertEqual(expected_id, section.section_id)
        self.assertEqual(expected_previous_id, section.previous_id)
        self.assertEqual(expected_next_id, section.next_id)

    def append_notifications(self, *range_args):
        for i in range(*range_args):
            item = 'item{}'.format(i + 1)
            self.append_notification(item)

    def create_notification_log(self, section_size):
        return RecordManagerNotificationLog(self.entity_record_manager, section_size)

    def construct_entity_record_manager(self):
        return self.factory.construct_integer_sequenced_record_manager()

    def append_notification(self, item):
        sequenced_item = self.entity_record_manager.sequenced_item_class(
            uuid4(),
            0,
            get_topic(DomainEvent),
            item
        )
        self.entity_record_manager.record_sequenced_items(sequenced_item)


class TestNotificationLog(NotificationLogTestCase):

    def test(self):
        # Build notification log.
        section_size = 5
        notification_log = self.create_notification_log(section_size=section_size)

        # Check the sections.
        section = notification_log['current']
        self.assertEqual('1,5', section.section_id)
        self.assertEqual(0, len(list(section.items)))
        self.assertIsNone(section.previous_id)
        self.assertIsNone(section.previous_id)

        # Append notifications.
        self.append_notifications(13)

        # Check the sections.
        self.assert_section(notification_log, 'current', '11,15', 3, '6,10', None)
        self.assert_section(notification_log, '1,5', '1,5', section_size, None, '6,10')
        self.assert_section(notification_log, '6,10', '6,10', section_size, '1,5', '11,15')
        self.assert_section(notification_log, '11,15', '11,15', 3, '6,10', None)
        self.assert_section(notification_log, '16,20', '16,20', 0, '11,15', None)
        self.assert_section(notification_log, '21,25', '21,25', 0, '16,20', None)

        # Add some more notification.
        self.append_notifications(13, 24)

        # Check the notification log has been extended.
        self.assertEqual(len(list(notification_log['11,15'].items)), section_size)
        self.assertEqual(len(list(notification_log['16,20'].items)), section_size)
        self.assertEqual(len(list(notification_log['21,25'].items)), 4)
        self.assertEqual(len(list(notification_log['26,30'].items)), 0)

        # Check an section ID that can't be split by ',' results in a ValueError.
        with self.assertRaises(ValueError):
            _ = notification_log['invalid']


class TestBigArrayNotificationLog(TestNotificationLog):

    def test(self):
        self.section_size = 5
        super(TestBigArrayNotificationLog, self).test()

        # Check array size must be divisible by section size.
        with self.assertRaises(ValueError):
            BigArrayNotificationLog(self.big_array, section_size=6)

        # # Check the section ID must match the section size.
        # notification_log = BigArrayNotificationLog(self.big_array, self.section_size)
        # with self.assertRaises(ValueError):
        #     _ = notification_log['1,2']

        # # Check the section ID must be aligned to the array size.
        # with self.assertRaises(ValueError):
        #     _ = notification_log['2,6']

    def create_notification_log(self, section_size):
        self.big_array = self.create_big_array()
        return BigArrayNotificationLog(self.big_array, section_size=section_size)

    def create_big_array(self, big_array_id=None):
        big_array_id = uuid4() if big_array_id is None else big_array_id
        big_array_repo = BigArrayRepository(event_store=self.entity_event_store)
        big_array = big_array_repo[big_array_id]
        return big_array

    def append_notification(self, item):
        self.big_array.append(item)


class TestNotificationLogReader(NotificationLogTestCase):

    def test(self):
        # Build notification log.
        section_size = 5
        notification_log = self.create_notification_log(section_size=section_size)

        # Append 13 notifications.
        self.append_notifications(13)

        # Construct notification log reader.
        reader = NotificationLogReader(notification_log)

        # Check position.
        self.assertEqual(reader.position, 0)

        # Read all notifications.
        all_notifications = list(reader)
        self.assertEqual(13, len(all_notifications))

        # Check position.
        self.assertEqual(reader.position, 13)

        # Add some more items to the log.
        self.append_notifications(13, 21)

        # Read subsequent notifications.
        subsequent_notifications_notifications = list(reader)
        self.assertEqual(len(subsequent_notifications_notifications), 8)

        # Check position.
        self.assertEqual(reader.position, 21)

        subsequent_notifications_notifications = list(reader)
        self.assertEqual(len(subsequent_notifications_notifications), 0)

        # Set position.
        reader.seek(13)
        subsequent_notifications_notifications = list(reader)
        self.assertEqual(len(subsequent_notifications_notifications), 8)

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

        # Resume from a saved position.
        saved_position = 5
        advance_by = 3
        reader.seek(saved_position)
        self.assertEqual(reader.position, saved_position)
        reader.read_list(advance_by=advance_by)
        self.assertEqual(reader.position, saved_position + advance_by)

        # Read items between particular positions.
        # - check stops at end of slice, and position tracks ok
        self.assertEqual(reader[0]['id'], 1)
        self.assertEqual(reader.position, 1)

        self.assertEqual(next(reader)['id'], 2)
        self.assertEqual(reader.position, 2)

        reader.seek(5)
        self.assertEqual(next(reader)['id'], 6)
        self.assertEqual(reader.position, 6)

        reader.seek(0)
        list(reader)
        self.assertEqual(reader.position, 21)

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

        with self.assertRaises(StopIteration):
            next(reader)


class TestRemoteNotificationLog(NotificationLogTestCase):
    use_named_temporary_file = True

    def test_remote_notification_log(self):
        num_notifications = 42

        section_size = 5

        # Build a notification log (fixture).
        self.append_notifications(num_notifications)

        # Start a simple server.
        from wsgiref.util import setup_testing_defaults
        from wsgiref.simple_server import make_server

        port = 8080
        base_url = 'http://127.0.0.1:{}/notifications/'.format(port)

        def simple_app(environ, start_response):
            """Simple WSGI application."""
            setup_testing_defaults(environ)

            # Identify log and section from request.
            path_info = environ['PATH_INFO']
            try:
                section_id = path_info.strip('/').split('/')[-1]
            except ValueError:
                # Start response.
                status = '404 Not Found'
                headers = [('Content-type', 'text/plain; charset=utf-8')]
                start_response(status, headers)
                return []

            # Select the notification log.
            notification_log = self.create_notification_log(section_size)

            # Get serialized section.
            view = NotificationLogView(notification_log)
            section, is_archived = view.present_section(section_id)
            # Todo: Maybe redirect if the section ID is a mismatch, so
            # the URL is good for cacheing.

            # Start response.
            status = '200 OK'
            headers = [('Content-type', 'text/plain; charset=utf-8')]
            start_response(status, headers)

            # Return a list of lines.
            return [(line + '\n').encode('utf8') for line in section.split('\n')]

        httpd = make_server('', port, simple_app)
        print("Serving on port {}...".format(port))
        thread = Thread(target=httpd.serve_forever)
        thread.setDaemon(True)
        thread.start()
        try:
            # Use reader with client to read all items in remote feed after item 5.
            notification_log = RemoteNotificationLog(base_url)

            # Get all the items.
            notification_log_reader = NotificationLogReader(notification_log=notification_log)
            items_from_start = notification_log_reader.read_list()

            # Check we got all the items.
            self.assertEqual(len(items_from_start), num_notifications)
            self.assertEqual(items_from_start[0]['id'], 1)
            self.assertEqual(items_from_start[0]['state'], 'item1')
            self.assertEqual(items_from_start[0]['topic'], 'eventsourcing.domain.model.events#DomainEvent')
            expected_section_count = ceil(num_notifications / float(section_size))
            self.assertEqual(notification_log_reader.section_count, expected_section_count)

            # Get all the items from item 5.
            items_from_5 = list(notification_log_reader[section_size - 1:])

            # Check we got everything after item 5.
            self.assertEqual(len(items_from_5), num_notifications - section_size + 1)
            self.assertEqual(items_from_5[0]['id'], section_size)
            self.assertEqual(items_from_5[0]['topic'], 'eventsourcing.domain.model.events#DomainEvent')
            self.assertEqual(items_from_5[0]['state'], 'item{}'.format(section_size))
            expected_section_count = ceil(num_notifications / float(section_size))
            self.assertEqual(notification_log_reader.section_count, expected_section_count)

            # Check ValueError is raised for deserialization errors.
            with self.assertRaises(ValueError):
                notification_log.deserialize_section('invalid json')

        finally:
            httpd.shutdown()
            thread.join()
            httpd.server_close()


class TestNotificationLogWithDjango(DjangoTestCase, TestNotificationLog):
    pass


class TestBigArrayNotificationLogWithDjango(DjangoTestCase, TestBigArrayNotificationLog):
    pass


class TestBigArrayNotificationLogWithCassandra(WithCassandraRecordManagers, TestBigArrayNotificationLog):
    pass
