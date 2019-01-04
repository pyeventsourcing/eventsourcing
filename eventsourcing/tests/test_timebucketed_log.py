import datetime
from time import sleep
from uuid import uuid4

from eventsourcing.domain.model.timebucketedlog import Timebucketedlog, bucket_duration, bucket_starts, \
    make_timebucket_id, start_new_timebucketedlog
from eventsourcing.infrastructure.repositories.timebucketedlog_repo import TimebucketedlogRepo
from eventsourcing.infrastructure.timebucketedlog_reader import TimebucketedlogReader
from eventsourcing.tests.base import notquick
from eventsourcing.tests.sequenced_item_tests.base import WithEventPersistence
from eventsourcing.tests.sequenced_item_tests.test_cassandra_record_manager import \
    WithCassandraRecordManagers
from eventsourcing.tests.sequenced_item_tests.test_sqlalchemy_record_manager import \
    SQLAlchemyRecordManagerTestCase
from eventsourcing.utils.times import decimaltimestamp


class TimebucketedlogTestCase(WithEventPersistence):

    def test_entity_lifecycle(self):
        self.log_repo = TimebucketedlogRepo(self.entity_event_store)
        log_name = uuid4()
        log = self.log_repo.get_or_create(log_name=log_name, bucket_size='year')
        log = self.log_repo[log_name]
        self.assertIsInstance(log, Timebucketedlog)
        self.assertEqual(log.name, log_name)
        self.assertEqual(log.bucket_size, 'year')

        # Append some messages to the log.
        message1 = 'This is message 1'
        message2 = 'This is message 2'
        message3 = 'This is message 3'
        message4 = 'This is message 4'
        message5 = 'This is message 5'
        message6 = 'This is message 6'
        event1 = log.log_message(message1)
        event2 = log.log_message(message2)
        event3 = log.log_message(message3)
        halfway = decimaltimestamp()
        event4 = log.log_message(message4)
        event5 = log.log_message(message5)
        event6 = log.log_message(message6)

        # Read messages from the log.
        reader = TimebucketedlogReader(log, event_store=self.log_event_store)
        messages = list(reader.get_messages(is_ascending=False))
        self.assertEqual(len(messages), 6)
        self.assertEqual(messages[0], message6)
        self.assertEqual(messages[1], message5)
        self.assertEqual(messages[2], message4)
        self.assertEqual(messages[3], message3)
        self.assertEqual(messages[4], message2)
        self.assertEqual(messages[5], message1)

        # Check we can get all the messages (query running in ascending order).
        messages = list(reader.get_messages(is_ascending=True))
        self.assertEqual(len(messages), 6)
        self.assertEqual(messages[0], message1)
        self.assertEqual(messages[1], message2)
        self.assertEqual(messages[2], message3)
        self.assertEqual(messages[3], message4)
        self.assertEqual(messages[4], message5)
        self.assertEqual(messages[5], message6)

        # Check we can get messages after halfway (query running in descending order).
        messages = list(reader.get_messages(gt=halfway, is_ascending=False))
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0], message6)
        self.assertEqual(messages[1], message5)
        self.assertEqual(messages[2], message4)

        # Check we can get messages until halfway (query running in descending order).
        messages = list(reader.get_messages(lte=halfway, is_ascending=False))
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0], message3)
        self.assertEqual(messages[1], message2)
        self.assertEqual(messages[2], message1)

        # Check we can get messages until halfway (query running in ascending order).
        messages = list(reader.get_messages(lte=halfway, is_ascending=True))
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0], message1)
        self.assertEqual(messages[1], message2)
        self.assertEqual(messages[2], message3)

        # Check we can get messages after halfway (query running in ascending order).
        messages = list(reader.get_messages(gt=halfway, is_ascending=True))
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0], message4)
        self.assertEqual(messages[1], message5)
        self.assertEqual(messages[2], message6)

        # Check we can get last three messages (query running in descending order).
        messages = list(reader.get_messages(limit=3, is_ascending=False))
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0], message6)
        self.assertEqual(messages[1], message5)
        self.assertEqual(messages[2], message4)

        # Check we can get first three messages (query running in ascending order).
        messages = list(reader.get_messages(limit=3, is_ascending=True))
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0], message1)
        self.assertEqual(messages[1], message2)
        self.assertEqual(messages[2], message3)

        # Check we can get last line (query running in descending order).
        messages = list(reader.get_messages(limit=1, gt=halfway, is_ascending=False))
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0], message6)

        # Check we can get the first line after halfway (query running in ascending order).
        messages = list(reader.get_messages(limit=1, gt=halfway, is_ascending=True))
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0], message4)

        # Check we can get the first line before halfway (query running in descending order).
        messages = list(reader.get_messages(limit=1, lte=halfway, is_ascending=False))
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0], message3)

        # Check we can get the first line (query running in ascending order).
        messages = list(reader.get_messages(limit=1, lte=halfway, is_ascending=True))
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0], message1)

        # Check there isn't a line after the last line (query running in ascending order).
        messages = list(reader.get_messages(limit=1, gt=event6.timestamp, is_ascending=True))
        self.assertEqual(len(messages), 0)

        # Check there is nothing somehow both after and until halfway.
        messages = list(reader.get_messages(gt=halfway, lte=halfway))
        self.assertEqual(len(messages), 0)

    @notquick
    def test_buckets_size_second(self):
        # Start new log.
        log = start_new_timebucketedlog(name=uuid4(), bucket_size='second')

        # Write messages across the time interval
        start = datetime.datetime.now()
        number_of_messages = 300
        events = []
        for i in range(number_of_messages):
            message_logged = log.log_message(str(i))
            events.append(message_logged)
            sleep(0.01)
        self.assertGreater(datetime.datetime.now() - start, datetime.timedelta(seconds=1))

        # Get the messages in descending order.
        reader = TimebucketedlogReader(log, self.log_event_store)
        messages = list(reader.get_messages(is_ascending=False, page_size=10))
        self.assertEqual(len(messages), number_of_messages)

        # Expect the order of the messages is the reverse of the created order.
        self.assertEqual(messages, list(reversed([str(i) for i in range(number_of_messages)])))

        # Get the messages in ascending order.
        messages = list(reader.get_messages(is_ascending=True, page_size=10))
        self.assertEqual(len(messages), number_of_messages)

        # Expect the order of the messages is the same as the created order.
        self.assertEqual(messages, [str(i) for i in range(number_of_messages)])

        # Get a limited number of messages in descending order.
        limit = 150
        messages = list(reader.get_messages(is_ascending=False, page_size=10, limit=limit))
        self.assertLess(limit, number_of_messages)
        self.assertEqual(len(messages), limit)

        # Expect the order of the messages is the reverse of the created order.
        self.assertEqual(messages, list(reversed([str(i) for i in range(number_of_messages)]))[:limit])

        # Get a limited number of messages in ascending order.
        limit = 150
        messages = list(reader.get_messages(is_ascending=True, page_size=10, limit=limit))
        self.assertLess(limit, number_of_messages)
        self.assertEqual(len(messages), limit)

        # Expect the order of the messages is the same as the created order.
        self.assertEqual(messages, [str(i) for i in range(limit)])

        # Get a limited number of messages in descending order from the midpoint down.
        limit = 110
        midpoint = events[150].timestamp
        messages = list(reader.get_messages(is_ascending=False, page_size=10, limit=limit, lt=midpoint))
        self.assertLess(limit, number_of_messages)
        self.assertEqual(len(messages), limit)

        # Expect the order of the messages is the reverse of the created order.
        self.assertEqual(messages, list(reversed([str(i) for i in range(150 - limit, 150)])))

        # Get a limited number of messages in ascending order from the midpoint up.
        limit = 110
        midpoint = events[149].timestamp
        messages = list(reader.get_messages(is_ascending=True, page_size=10, limit=limit, gt=midpoint))
        self.assertLess(limit, number_of_messages)
        self.assertEqual(len(messages), limit)

        # Expect the order of the messages is the same as the created order.
        self.assertEqual(messages, [str(i) for i in range(150, 150 + limit)])

        # Get a limited number of messages in descending order above the midpoint down.
        limit = 200
        midpoint = events[150].timestamp
        messages = list(reader.get_messages(is_ascending=False, page_size=10, limit=limit, gte=midpoint))
        self.assertLess(limit, number_of_messages)
        self.assertEqual(len(messages), 150)

        # Expect the order of the messages is the reverse of the created order.
        self.assertEqual(messages, list(reversed([str(i) for i in range(150, 300)])))

        # Get a limited number of messages in ascending order below the midpoint up.
        limit = 200
        midpoint = events[149].timestamp
        messages = list(reader.get_messages(is_ascending=True, page_size=10, limit=limit, lte=midpoint))
        self.assertLess(limit, number_of_messages)
        self.assertEqual(len(messages), 150)

        # Expect the order of the messages is the same as the created order.
        self.assertEqual(messages, [str(i) for i in range(150)])

        #
        # Use the last position to start part way through.
        limit = 20
        last_position = reader.position
        messages = reader.get_messages(is_ascending=True, page_size=10, limit=limit, gt=last_position)
        messages = list(messages)
        self.assertEqual(len(messages), limit)

        # Expect the order of the messages is the same as the created order.
        self.assertEqual(messages, [str(i) for i in range(150, 150 + limit)])

        # Do it again.
        last_position = reader.position
        messages = reader.get_messages(is_ascending=True, page_size=10, limit=limit, gt=last_position)
        messages = list(messages)
        self.assertEqual(len(messages), limit)

        # Expect the order of the messages is the same as the created order.
        self.assertEqual(messages, [str(i) for i in range(150 + limit, 150 + limit * 2)])

        # Go back.
        last_position = reader.position
        messages = reader.get_messages(is_ascending=False, page_size=10, limit=limit, lt=last_position)
        messages = list(messages)
        self.assertEqual(len(messages), limit)

        # Expect the order of the messages is the reverse of the created order.
        self.assertEqual(messages, [str(i) for i in range(148 + limit * 2, 148 + limit, -1)])

        # Go back.
        last_position = reader.position
        messages = reader.get_messages(is_ascending=False, page_size=10, limit=limit, lt=last_position)
        messages = list(messages)
        self.assertEqual(len(messages), limit)

        # Expect the order of the messages is the reverse of the created order.
        self.assertEqual(messages, [str(i) for i in range(128 + limit * 2, 128 + limit, -1)])

        # Go back.
        last_position = reader.position
        messages = reader.get_messages(is_ascending=False, page_size=10, limit=limit, lt=last_position)
        messages = list(messages)
        self.assertEqual(len(messages), limit)

        # Expect the order of the messages is the reverse of the created order.
        self.assertEqual(messages, [str(i) for i in range(108 + limit * 2, 108 + limit, -1)])

        # Repeat.
        messages = reader.get_messages(is_ascending=False, page_size=10, limit=limit, lt=last_position)
        messages = list(messages)
        self.assertEqual(len(messages), limit)

        # Expect the order of the messages is the reverse of the created order.
        self.assertEqual(messages, [str(i) for i in range(108 + limit * 2, 108 + limit, -1)])

    def test_buckets_of_all_sizes(self):
        # Start new second sized log.
        log_id2 = uuid4()
        log = start_new_timebucketedlog(name=log_id2, bucket_size='second')
        log.log_message('message')

        # Get the messages.
        reader = TimebucketedlogReader(log, self.log_event_store)
        self.assertTrue(len(list(reader.get_messages())))

        # Start new minute sized log.
        log_id3 = uuid4()
        log = start_new_timebucketedlog(name=log_id3, bucket_size='minute')
        log.log_message('message')

        # Get the messages.
        reader = TimebucketedlogReader(log, self.log_event_store)
        self.assertTrue(len(list(reader.get_messages())))

        # Start new hour sized log.
        log_id4 = uuid4()
        log = start_new_timebucketedlog(name=log_id4, bucket_size='hour')
        log.log_message('message')

        # Get the messages.
        reader = TimebucketedlogReader(log, self.log_event_store)
        self.assertTrue(len(list(reader.get_messages())))

        # Start new day sized log.
        log_id5 = uuid4()
        log = start_new_timebucketedlog(name=log_id5, bucket_size='day')
        log.log_message('message')

        # Get the messages.
        reader = TimebucketedlogReader(log, self.log_event_store)
        self.assertTrue(len(list(reader.get_messages())))

        # Start new month sized log.
        log_id6 = uuid4()
        log = start_new_timebucketedlog(name=log_id6, bucket_size='month')
        log.log_message('message')

        # Get the messages.
        reader = TimebucketedlogReader(log, self.log_event_store)
        self.assertTrue(len(list(reader.get_messages())))

        # Start new year sized log.
        log_id7 = uuid4()
        log = start_new_timebucketedlog(name=log_id7, bucket_size='year')
        log.log_message('message')

        # Get the messages.
        reader = TimebucketedlogReader(log, self.log_event_store)
        self.assertTrue(len(list(reader.get_messages())))

        # Start new default sized log.
        log_id8 = uuid4()
        log = start_new_timebucketedlog(name=log_id8)
        log.log_message('message')

        # Get the messages.
        reader = TimebucketedlogReader(log, self.log_event_store)
        self.assertTrue(len(list(reader.get_messages())))

        # Start new invalid sized log.
        with self.assertRaises(ValueError):
            log_id9 = uuid4()
            log = start_new_timebucketedlog(name=log_id9, bucket_size='invalid')

        # Check the helper methods are protected against invalid bucket sizes.
        with self.assertRaises(ValueError):
            log_id10 = uuid4()
            make_timebucket_id(log_id10, decimaltimestamp(), bucket_size='invalid')

        with self.assertRaises(ValueError):
            bucket_starts(decimaltimestamp(), bucket_size='invalid')

        with self.assertRaises(ValueError):
            bucket_duration(bucket_size='invalid')


class TestLogWithCassandra(WithCassandraRecordManagers, TimebucketedlogTestCase):
    pass


class TestLogWithSQLAlchemy(SQLAlchemyRecordManagerTestCase, TimebucketedlogTestCase):
    pass


del(TimebucketedlogTestCase)
del(WithEventPersistence)
