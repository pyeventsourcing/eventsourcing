from math import floor
from uuid import uuid1

import six

from eventsourcing.application.example.base import ExampleApplication
from eventsourcing.application.example.with_cassandra import ExampleApplicationWithCassandra
from eventsourcing.application.example.with_pythonobjects import ExampleApplicationWithPythonObjects
from eventsourcing.application.example.with_sqlalchemy import ExampleApplicationWithSQLAlchemy
from eventsourcing.domain.model.example import register_new_example, Example
from eventsourcing.domain.model.log import get_logger, start_new_log
from eventsourcing.domain.services.transcoding import make_stored_entity_id
from eventsourcing.infrastructure.log_reader import get_log_reader, LogReader
from eventsourcing.infrastructure.stored_event_repos.with_cassandra import create_cassandra_keyspace_and_tables, \
    drop_cassandra_keyspace
from eventsourcing.domain.services.cipher import AESCipher
from eventsourcing.tests.unit_test_cases import AbstractTestCase
from eventsourcing.tests.test_utils import utc_now


class PerformanceTestCase(AbstractTestCase):

    def setUp(self):
        super(PerformanceTestCase, self).setUp()
        self.app = self.create_app()
        assert isinstance(self.app, ExampleApplication)

    def create_app(self):
        """Returns instance of application object to be tested.

        Sub-classes are required to override this method to return an application object.
        """
        raise NotImplementedError

    def test_entity_performance(self):
        """
        Reports on the performance of Example entity and repo.

        NB: This test doesn't actually check anything, so it isn't really a test.
        """

        # Initialise dict of entities.
        self.entities = {}

        report_name = type(self).__name__[4:]
        print("\n\n{} report:\n".format(report_name))

        repetitions = 10

        # NB: Use range(1, 5) to test whether we can get more than 10000 event from Cassandra.
        for i in six.moves.range(0, 5):
            # Setup a number of entities, with different lengths of event history.
            payload = 3
            # payload = str([uuid4().hex for _ in six.moves.range(100000)])
            example = register_new_example(a=1, b=payload)
            self.entities[i] = example

            # Beat a number of times.
            start_beating = utc_now()
            num_beats = int(floor(10 ** i))
            for _ in six.moves.range(num_beats):
                example.beat_heart()
            time_beating = utc_now() - start_beating
            print("Time to beat {} times: {:.2f}s ({:.0f} beats/s, {:.6f}s each)"
                  "".format(num_beats, time_beating, num_beats / time_beating, time_beating / num_beats))

            # Get the last n events from the repo.
            def last_n(n):
                n = min(n, num_beats + 1)
                stored_entity_id = make_stored_entity_id('Example', example.id)
                repo = self.app.example_repo.event_player.event_store.stored_event_repo

                start_last_n = utc_now()
                last_n_stored_events = []
                for _ in six.moves.range(repetitions):
                    last_n_stored_events = repo.get_most_recent_events(stored_entity_id, limit=n)
                time_last_n = (utc_now() - start_last_n) / repetitions

                num_retrieved_events = len(list(last_n_stored_events))
                events_per_second = num_retrieved_events / time_last_n
                print(("Time to get last {:>"+str(i+1)+"} events after {} events: {:.6f}s ({:.0f} events/s)"
                      "").format(n, num_beats + 1, time_last_n, events_per_second))

            for j in range(0, i+1):
                last_n(10**j)

            # Get the entity by replaying all events (which it must since there isn't a snapshot).
            start_replay = utc_now()
            for _ in six.moves.range(repetitions):
                example = self.app.example_repo[example.id]
                assert isinstance(example, Example)
                heartbeats = example.count_heartbeats()
                assert heartbeats == num_beats, (heartbeats, num_beats)

            time_replaying = (utc_now() - start_replay) / repetitions
            print("Time to replay {} beats: {:.2f}s ({:.0f} beats/s, {:.6f}s each)"
                  "".format(num_beats, time_replaying, num_beats / time_replaying, time_replaying / num_beats))

            # Take snapshot, and beat heart a few more times.
            self.app.example_repo.event_player.take_snapshot(example.id, until=uuid1().hex)

            extra_beats = 4
            for _ in six.moves.range(extra_beats):
                example.beat_heart()
            num_beats += extra_beats

            # Get the entity using snapshot and replaying events since the snapshot.
            start_replay = utc_now()
            for _ in six.moves.range(repetitions):
                example = self.app.example_repo[example.id]
            time_replaying = (utc_now() - start_replay) / repetitions

            events_per_second = (extra_beats + 1) / time_replaying  # +1 for the snapshot event
            beats_per_second = num_beats / time_replaying
            print("Time to replay snapshot with {} extra beats: {:.6f}s ({:.0f} events/s, {:.0f} beats/s)"
                  "".format(extra_beats, time_replaying, events_per_second, beats_per_second))
            
            print("")

    def test_log_performance(self):
        log = start_new_log('example', bucket_size='year')
        logger = get_logger(log)
        log_reader = get_log_reader(log, self.app.event_store)

        # Write a load of messages.
        start_write = utc_now()
        number_of_messages = 111
        events = []
        for i in range(number_of_messages):
            event = logger.info('Logger message number {}'.format(i))
            events.append(event)
        time_to_write = (utc_now() - start_write)
        print("Time to log {} messages: {:.2f}s ({:.0f} messages/s, {:.6f}s each)"
              "".format(number_of_messages, time_to_write, number_of_messages/ time_to_write,
                        time_to_write / number_of_messages))

        # Read pages of messages in descending order.
        # - get a limited number until a time, then use the earliest in that list as the position
        position = events[-1].domain_event_id

        page_size = 10

        # Page back through the log in reverse chronological order.
        previous_position = None
        next_position = None
        count_pages = 0
        total_time_to_read = 0
        total_num_reads = 0
        while True:
            start_read = utc_now()
            page_of_events, next_position = self.get_message_logged_events_and_next_position(log_reader, position, page_size)
            time_to_read = (utc_now() - start_read)
            total_time_to_read += time_to_read
            total_num_reads += 1
            count_pages += 1
            if next_position is None:
                break
            else:
                previous_position, position = position, next_position

        # Check we got to the end of the line.
        self.assertEqual(count_pages, 11)
        self.assertIsNone(next_position)
        self.assertTrue(previous_position)

        # Page forward through the log in chronological order.
        count_pages = 0
        position = None
        while True:
            start_read = utc_now()
            page_of_events, next_position = self.get_message_logged_events_and_next_position(log_reader, position, page_size, is_ascending=True)
            time_to_read = (utc_now() - start_read)
            total_time_to_read += time_to_read
            total_num_reads += 1
            count_pages += 1
            if next_position is None:
                break
            else:
                position = next_position

        self.assertEqual(count_pages, 11)
        self.assertIsNone(next_position)
        self.assertTrue(previous_position)

        reads_per_second = total_num_reads / total_time_to_read
        messages_per_second = reads_per_second * number_of_messages
        print("Time to read {} pages of logged messages: {:.6f}s ({:.0f} pages/s, {:.0f} messages/s))"
              "".format(total_num_reads, total_time_to_read, reads_per_second, messages_per_second))

    def get_message_logged_events_and_next_position(self, log_reader, position, page_size, is_ascending=False):
        assert isinstance(log_reader, LogReader), type(log_reader)
        assert isinstance(position, (six.string_types, type(None))), type(position)
        assert isinstance(page_size, six.integer_types), type(page_size)
        assert isinstance(is_ascending, bool)
        if is_ascending:
            after = position
            until = None
        else:
            after = None
            until = position

        events = log_reader.get_events(after=after, until=until, limit=page_size + 1, is_ascending=is_ascending)
        events = list(events)
        if len(events) == page_size + 1:
            next_position = events.pop().domain_event_id
        else:
            next_position = None
        return events, next_position


class TestCassandraPerformance(PerformanceTestCase):

    def create_app(self):
        return ExampleApplicationWithCassandra()

    def setUp(self):
        super(TestCassandraPerformance, self).setUp()

        # Setup the keyspace and column family for stored events.
        create_cassandra_keyspace_and_tables()

    def tearDown(self):
        # Drop the keyspace.
        drop_cassandra_keyspace()

        # Close the application.
        self.app.close()

        super(TestCassandraPerformance, self).tearDown()


class TestEncryptionPerformance(TestCassandraPerformance):

    def create_app(self):
        cipher = AESCipher(aes_key='0123456789abcdef')
        return ExampleApplicationWithCassandra(cipher=cipher, always_encrypt_stored_events=True)


class TestSQLAlchemyPerformance(PerformanceTestCase):

    def create_app(self):
        return ExampleApplicationWithSQLAlchemy(db_uri='sqlite:///:memory:')

    def tearDown(self):
        # Close the application.
        self.app.close()


class TestPythonObjectsPerformance(PerformanceTestCase):

    def create_app(self):
        # Setup the example application.
        return ExampleApplicationWithPythonObjects()

    def tearDown(self):
        # Close the application.
        self.app.close()
