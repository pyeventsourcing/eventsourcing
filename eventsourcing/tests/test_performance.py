import time
from math import floor
from unittest import skip
from uuid import uuid4

from eventsourcing.domain.model.timebucketedlog import start_new_timebucketedlog
from eventsourcing.example.domainmodel import Example, create_new_example
from eventsourcing.infrastructure.base import AbstractSequencedItemRecordManager
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.iterators import SequencedItemIterator
from eventsourcing.infrastructure.sqlalchemy.records import IntegerSequencedNoIDRecord, IntegerSequencedWithIDRecord, \
    TimestampSequencedNoIDRecord, TimestampSequencedWithIDRecord
from eventsourcing.infrastructure.timebucketedlog_reader import TimebucketedlogReader, get_timebucketedlog_reader
from eventsourcing.tests.base import notquick
from eventsourcing.tests.example_application_tests import base
from eventsourcing.tests.example_application_tests.test_example_application_with_encryption import WithEncryption
from eventsourcing.tests.sequenced_item_tests.test_cassandra_record_manager import WithCassandraRecordManagers
from eventsourcing.tests.sequenced_item_tests.test_django_record_manager import DjangoTestCase
from eventsourcing.tests.sequenced_item_tests.test_popo_record_manager import PopoTestCase
from eventsourcing.tests.sequenced_item_tests.test_sqlalchemy_record_manager import SQLAlchemyRecordManagerTestCase


@notquick
class PerformanceTestCase(base.WithExampleApplication):
    drop_tables = True

    def test_entity_performance(self):
        """
        Reports on the performance of Example entity and repo.

        NB: This test doesn't actually assert anything, so it isn't really a test.
        """

        with self.construct_application() as app:

            # Initialise dict of entities.
            self.entities = {}

            report_name = type(self).__name__[4:]
            print("\n\n{} report:\n".format(report_name))

            repetitions = 10  # 10

            # NB: Use range(1, 5) to test whether we can get more than 10000 items from Cassandra.
            # Setup a number of entities, with different lengths of event history.
            for i in range(0, 4):

                # Initialise table with other entities.
                num_other_entities = i
                filling = []
                for _ in range(num_other_entities):
                    filling.append(create_new_example(a=1, b=2))

                # b = str([uuid4().hex for _ in range(100000)])
                b = 2
                example = create_new_example(a=1, b=b)
                self.entities[i] = example

                # Beat a number of times.
                num_beats = int(floor(10 ** i))
                start_beating = time.time()
                for _ in range(num_beats):
                    # print("Beat example")
                    example.beat_heart()

                    for other in filling:
                        other.beat_heart()

                total_beats = num_beats * (1 + len(filling))
                time_beating = time.time() - start_beating
                try:
                    beats_per_second = total_beats / time_beating
                except ZeroDivisionError as e:
                    print("Warning: beats per second {} / {}: {}".format(total_beats, time_beating, e))
                    beats_per_second = -999999999999.99999999
                try:
                    beat_period = time_beating / total_beats
                except ZeroDivisionError as e:
                    print("Warning: beat period {} / {}: {}".format(time_beating, total_beats, e))
                    beat_period = -999999999999.9999999

                print("Time to beat {} times: {:.4f}s ({:.0f} beats/s, {:.6f}s each)"
                      "".format(num_beats, time_beating / (1 + num_other_entities), beats_per_second, beat_period))

                # Get the last n events from the repo.
                def last_n(n):
                    n = min(n, num_beats + 1)
                    assert isinstance(app.example_repository.event_store, EventStore)
                    ars = app.example_repository.event_store.record_manager
                    assert isinstance(ars, AbstractSequencedItemRecordManager)

                    start_last_n = time.time()
                    last_n_stored_events = []
                    for _ in range(repetitions):
                        iterator = SequencedItemIterator(
                            record_manager=ars,
                            sequence_id=example.id,
                            limit=n,
                            is_ascending=False,
                        )
                        last_n_stored_events = list(iterator)
                    time_last_n = (time.time() - start_last_n) / repetitions

                    num_retrieved_events = len(last_n_stored_events)
                    events_per_second = num_retrieved_events / time_last_n
                    print(("Time to get last {:>" + str(i + 1) + "} events after {} events: {:.6f}s ({:.0f} events/s)"
                                                                 "").format(n, num_beats + 1, time_last_n,
                                                                            events_per_second))

                for j in range(0, i + 1):
                    last_n(10 ** j)

                # Get the entity by replaying all events (which it must since there isn't a snapshot).
                start_replay = time.time()
                for _ in range(repetitions):
                    example = app.example_repository[example.id]
                    assert isinstance(example, Example)
                    heartbeats = example.count_heartbeats()
                    assert heartbeats == num_beats, (heartbeats, num_beats)

                time_replaying = (time.time() - start_replay) / repetitions
                print("Time to replay {} beats: {:.2f}s ({:.0f} beats/s, {:.6f}s each)"
                      "".format(num_beats, time_replaying, num_beats / time_replaying, time_replaying / num_beats))

                # Take snapshot, and beat heart a few more times.
                app.example_repository.take_snapshot(example.id, lt=example.__version__)

                extra_beats = 4
                for _ in range(extra_beats):
                    example.beat_heart()
                num_beats += extra_beats

                # Get the entity using snapshot and replaying events since the snapshot.
                start_replay = time.time()
                for _ in range(repetitions):
                    example = app.example_repository[example.id]
                time_replaying = (time.time() - start_replay) / repetitions

                events_per_second = (extra_beats + 1) / time_replaying  # +1 for the snapshot event
                beats_per_second = num_beats / time_replaying
                print("Time to replay snapshot with {} extra beats: {:.6f}s ({:.0f} events/s, {:.0f} beats/s)"
                      "".format(extra_beats, time_replaying, events_per_second, beats_per_second))

                print("")

    def test_log_performance(self):

        with self.construct_application() as app:
            example_id = uuid4()
            log = start_new_timebucketedlog(example_id, bucket_size='year')
            log_reader = get_timebucketedlog_reader(log, app.log_event_store)

            # Write a load of messages.
            start_write = time.time()
            number_of_messages = 111
            events = []
            for i in range(number_of_messages):
                event = log.log_message('Logger message number {}'.format(i))
                events.append(event)
            time_to_write = (time.time() - start_write)
            print("Time to log {} messages: {:.2f}s ({:.0f} messages/s, {:.6f}s each)"
                  "".format(number_of_messages, time_to_write, number_of_messages / time_to_write,
                            time_to_write / number_of_messages))

            # Read pages of messages in descending order.
            # - get a limited number until a time, then use the earliest in that list as the position
            position = events[-1].timestamp

            page_size = 10

            # Page back through the log in reverse chronological order.
            previous_position = None
            count_pages = 0
            total_time_to_read = 0
            total_num_reads = 0
            while True:
                start_read = time.time()
                page_of_events, next_position = self.get_message_logged_events_and_next_position(log_reader, position,
                                                                                                 page_size)
                time_to_read = (time.time() - start_read)
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
                start_read = time.time()
                page_of_events, next_position = self.get_message_logged_events_and_next_position(log_reader, position,
                                                                                                 page_size,
                                                                                                 is_ascending=True)
                time_to_read = (time.time() - start_read)
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
        assert isinstance(log_reader, TimebucketedlogReader), type(log_reader)
        assert isinstance(page_size, int), type(page_size)
        assert isinstance(is_ascending, bool)
        if is_ascending:
            gt = position
            lt = None
        else:
            lt = position
            gt = None

        events = log_reader.get_events(gt=gt, lt=lt, limit=page_size + 1, is_ascending=is_ascending)
        events = list(events)
        if len(events) == page_size + 1:
            next_position = events.pop().timestamp
        else:
            next_position = None
        return events, next_position


@notquick
class TestCassandraPerformance(WithCassandraRecordManagers, PerformanceTestCase):
    pass


@notquick
class TestDjangoPerformance(DjangoTestCase, PerformanceTestCase):
    pass


@notquick
class TestDjangoPerformanceWithEncryption(WithEncryption, TestDjangoPerformance):
    pass


@notquick
class TestPopoPerformance(PopoTestCase, PerformanceTestCase):
    @skip("Popo record manager only supports sequencing with integers")
    def test_log_performance(self):
        pass


@notquick
class TestCassandraPerformanceWithEncryption(WithEncryption, TestCassandraPerformance):
    pass


@notquick
class TestSQLAlchemyPerformance(SQLAlchemyRecordManagerTestCase, PerformanceTestCase):
    def construct_entity_record_manager(self):
        return self.factory.construct_integer_sequenced_record_manager(
            record_class=IntegerSequencedWithIDRecord
        )

    def construct_log_record_manager(self):
        return self.factory.construct_timestamp_sequenced_record_manager(
            record_class=TimestampSequencedWithIDRecord
        )


@notquick
class TestSQLAlchemyPerformanceNoID(TestSQLAlchemyPerformance):

    def construct_entity_record_manager(self):
        return self.factory.construct_integer_sequenced_record_manager(
            record_class=IntegerSequencedNoIDRecord
        )

    def construct_log_record_manager(self):
        return self.factory.construct_timestamp_sequenced_record_manager(
            record_class=TimestampSequencedNoIDRecord
        )


@notquick
class TestSQLAlchemyPerformanceWithEncryption(WithEncryption, TestSQLAlchemyPerformance):
    pass


# Avoid running abstract test case.
del (PerformanceTestCase)
