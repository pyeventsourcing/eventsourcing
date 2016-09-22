import datetime
from time import sleep
from uuid import uuid1

from eventsourcing.domain.model.events import assert_event_handlers_empty
from eventsourcing.domain.model.log import get_logger, Logger, start_new_log, Log
from eventsourcing.infrastructure.event_sourced_repos.log_repo import LogRepo
from eventsourcing.infrastructure.log_reader import get_log_reader
from eventsourcing.infrastructure.event_store import EventStore
from eventsourcing.infrastructure.persistence_subscriber import PersistenceSubscriber
from eventsourcing.tests.test_stored_event_repository_cassandra import CassandraTestCase
from eventsourcing.tests.test_stored_event_repository_python_objects import PythonObjectsTestCase
from eventsourcing.tests.test_stored_event_repository_sqlalchemy import SQLAlchemyTestCase
from eventsourcing.tests.test_stored_events import AbstractTestCase


class LogTestCase(AbstractTestCase):
    @property
    def stored_event_repo(self):
        """
        Returns a stored event repository.

        Concrete log test cases will provide this method.
        """
        raise NotImplementedError

    def setUp(self):
        super(LogTestCase, self).setUp()

        # Check we're starting clean, event handler-wise.
        assert_event_handlers_empty()

        # Setup the persistence subscriber.
        self.event_store = EventStore(self.stored_event_repo)
        self.persistence_subscriber = PersistenceSubscriber(event_store=self.event_store)

        self.log_repo = LogRepo(self.event_store)

    def tearDown(self):
        # Close the persistence subscriber.
        self.persistence_subscriber.close()

        super(LogTestCase, self).tearDown()

        # Check we finished clean, event handler-wise.
        assert_event_handlers_empty()

    def test_entity_lifecycle(self):
        log = self.log_repo.get_or_create(log_name='log1', bucket_size='year')
        self.assertIsInstance(log, Log)
        self.assertEqual(log.name, 'log1')
        self.assertEqual(log.bucket_size, 'year')

        # Test get_logger and get_log_reader().
        logger = get_logger(log)
        self.assertIsInstance(logger, Logger)
        message1 = 'This is message 1'
        message2 = 'This is message 2'
        message3 = 'This is message 3'
        message4 = 'This is message 4'
        message5 = 'This is message 5'
        message6 = 'This is message 6'
        event1 = logger.info(message1)
        event2 = logger.info(message2)
        event3 = logger.info(message3)
        halfway = uuid1().hex
        event4 = logger.info(message4)
        event5 = logger.info(message5)
        event6 = logger.info(message6)

        # Check we can get all the messages (query running in descending order).
        log_reader = get_log_reader(log, event_store=self.event_store)
        messages = list(log_reader.get_messages(is_ascending=False))
        self.assertEqual(len(messages), 6)
        self.assertEqual(messages[0], message6)
        self.assertEqual(messages[1], message5)
        self.assertEqual(messages[2], message4)
        self.assertEqual(messages[3], message3)
        self.assertEqual(messages[4], message2)
        self.assertEqual(messages[5], message1)

        # Check we can get all the messages (query running in ascending order).
        messages = list(log_reader.get_messages(is_ascending=True))
        self.assertEqual(len(messages), 6)
        self.assertEqual(messages[0], message1)
        self.assertEqual(messages[1], message2)
        self.assertEqual(messages[2], message3)
        self.assertEqual(messages[3], message4)
        self.assertEqual(messages[4], message5)
        self.assertEqual(messages[5], message6)

        # Check we can get messages after halfway (query running in descending order).
        messages = list(log_reader.get_messages(after=halfway, is_ascending=False))
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0], message6)
        self.assertEqual(messages[1], message5)
        self.assertEqual(messages[2], message4)

        # Check we can get messages until halfway (query running in descending order).
        messages = list(log_reader.get_messages(until=halfway, is_ascending=False))
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0], message3)
        self.assertEqual(messages[1], message2)
        self.assertEqual(messages[2], message1)

        # Check we can get messages until halfway (query running in ascending order).
        messages = list(log_reader.get_messages(until=halfway, is_ascending=True))
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0], message1)
        self.assertEqual(messages[1], message2)
        self.assertEqual(messages[2], message3)

        # Check we can get messages after halfway (query running in ascending order).
        messages = list(log_reader.get_messages(after=halfway, is_ascending=True))
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0], message4)
        self.assertEqual(messages[1], message5)
        self.assertEqual(messages[2], message6)

        # Check we can get last three messages (query running in descending order).
        messages = list(log_reader.get_messages(limit=3, is_ascending=False))
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0], message6)
        self.assertEqual(messages[1], message5)
        self.assertEqual(messages[2], message4)

        # Check we can get first three messages (query running in ascending order).
        messages = list(log_reader.get_messages(limit=3, is_ascending=True))
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0], message1)
        self.assertEqual(messages[1], message2)
        self.assertEqual(messages[2], message3)

        # Check we can get last line (query running in descending order).
        messages = list(log_reader.get_messages(limit=1, after=halfway, is_ascending=False))
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0], message6)

        # Check we can get the first line after halfway (query running in ascending order).
        messages = list(log_reader.get_messages(limit=1, after=halfway, is_ascending=True))
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0], message4)

        # Check we can get the first line before halfway (query running in descending order).
        messages = list(log_reader.get_messages(limit=1, until=halfway, is_ascending=False))
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0], message3)

        # Check we can get the first line (query running in ascending order).
        messages = list(log_reader.get_messages(limit=1, until=halfway, is_ascending=True))
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0], message1)

        # Check there isn't a line after the last line (query running in ascending order).
        messages = list(log_reader.get_messages(limit=1, after=event6.domain_event_id, is_ascending=True))
        self.assertEqual(len(messages), 0)

        # Check there is nothing somehow both after and until halfway.
        messages = list(log_reader.get_messages(after=halfway, until=halfway))
        self.assertEqual(len(messages), 0)

    def test_buckets(self):
        # Start new log.
        log = start_new_log(name='log1', bucket_size='second')

        # Write messages across the time interval
        start = datetime.datetime.now()
        logger = get_logger(log)
        number_of_messages = 300
        events = []
        for i in range(number_of_messages):
            message_logged = logger.info(str(i))
            events.append(message_logged)
            sleep(0.01)
        self.assertGreater(datetime.datetime.now() - start, datetime.timedelta(seconds=1))

        # Get the messages in descending order.
        reader = get_log_reader(log, self.event_store)
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
        midpoint = events[150].domain_event_id
        messages = list(reader.get_messages(is_ascending=False, page_size=10, limit=limit, until=midpoint))
        self.assertLess(limit, number_of_messages)
        self.assertEqual(len(messages), limit)

        # Expect the order of the messages is the reverse of the created order.
        self.assertEqual(messages, list(reversed([str(i) for i in range(150 - limit, 150)])))

        # Get a limited number of messages in ascending order from the midpoint up.
        limit = 110
        midpoint = events[149].domain_event_id
        messages = list(reader.get_messages(is_ascending=True, page_size=10, limit=limit, after=midpoint))
        self.assertLess(limit, number_of_messages)
        self.assertEqual(len(messages), limit)

        # Expect the order of the messages is the same as the created order.
        self.assertEqual(messages, [str(i) for i in range(150, 150 + limit)])

        # Get a limited number of messages in descending order above the midpoint down.
        limit = 200
        midpoint = events[150].domain_event_id
        messages = list(reader.get_messages(is_ascending=False, page_size=10, limit=limit, after=midpoint))
        self.assertLess(limit, number_of_messages)
        self.assertEqual(len(messages), 150)

        # Expect the order of the messages is the reverse of the created order.
        self.assertEqual(messages, list(reversed([str(i) for i in range(150, 300)])))

        # Get a limited number of messages in ascending order below the midpoint up.
        limit = 200
        midpoint = events[149].domain_event_id
        messages = list(reader.get_messages(is_ascending=True, page_size=10, limit=limit, until=midpoint))
        self.assertLess(limit, number_of_messages)
        self.assertEqual(len(messages), 150)

        # Expect the order of the messages is the same as the created order.
        self.assertEqual(messages, [str(i) for i in range(150)])

        #
        # Use the last position to start part way through.
        limit = 20
        last_position = reader.position
        messages = reader.get_messages(is_ascending=True, page_size=10, limit=limit, after=last_position)
        messages = list(messages)
        self.assertEqual(len(messages), limit)

        # Expect the order of the messages is the same as the created order.
        self.assertEqual(messages, [str(i) for i in range(150, 150 + limit)])

        # Do it again.
        last_position = reader.position
        messages = reader.get_messages(is_ascending=True, page_size=10, limit=limit, after=last_position)
        messages = list(messages)
        self.assertEqual(len(messages), limit)

        # Expect the order of the messages is the same as the created order.
        self.assertEqual(messages, [str(i) for i in range(150 + limit, 150 + limit * 2)])

        # Go back.
        last_position = reader.position
        messages = reader.get_messages(is_ascending=False, page_size=10, limit=limit, until=last_position)
        messages = list(messages)
        self.assertEqual(len(messages), limit)

        # Expect the order of the messages is the reverse of the created order.
        self.assertEqual(messages, [str(i) for i in range(148 + limit * 2, 148 + limit, -1)])

        # Go back.
        last_position = reader.position
        messages = reader.get_messages(is_ascending=False, page_size=10, limit=limit, until=last_position)
        messages = list(messages)
        self.assertEqual(len(messages), limit)

        # Expect the order of the messages is the reverse of the created order.
        self.assertEqual(messages, [str(i) for i in range(128 + limit * 2, 128 + limit, -1)])

        # Go back.
        last_position = reader.position
        messages = reader.get_messages(is_ascending=False, page_size=10, limit=limit, until=last_position)
        messages = list(messages)
        self.assertEqual(len(messages), limit)

        # Expect the order of the messages is the reverse of the created order.
        self.assertEqual(messages, [str(i) for i in range(108 + limit * 2, 108 + limit, -1)])

        # Repeat.
        messages = reader.get_messages(is_ascending=False, page_size=10, limit=limit, until=last_position)
        messages = list(messages)
        self.assertEqual(len(messages), limit)

        # Expect the order of the messages is the reverse of the created order.
        self.assertEqual(messages, [str(i) for i in range(108 + limit * 2, 108 + limit, -1)])


class TestLogWithCassandra(CassandraTestCase, LogTestCase):
    pass


class TestLogWithPythonObjects(PythonObjectsTestCase, LogTestCase):
    pass


class TestLogWithSQLAlchemy(SQLAlchemyTestCase, LogTestCase):
    pass
