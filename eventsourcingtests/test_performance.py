from math import floor
from unittest.case import TestCase
from uuid import uuid1

import six
from cassandra.cqlengine.management import drop_keyspace

from eventsourcing.application.example.with_cassandra import ExampleApplicationWithCassandra
from eventsourcing.application.example.with_pythonobjects import ExampleApplicationWithPythonObjects
from eventsourcing.application.example.with_sqlalchemy import ExampleApplicationWithSQLAlchemy
from eventsourcing.application.with_cassandra import DEFAULT_CASSANDRA_KEYSPACE
from eventsourcing.domain.model.example import register_new_example
from eventsourcing.infrastructure.stored_events.cassandra_stored_events import create_cassandra_keyspace_and_tables
from eventsourcing.infrastructure.stored_events.transcoders import make_stored_entity_id
from eventsourcing.utils.time import utc_now


class PerformanceTestCase(TestCase):

    def setUp(self):
        self.skipTest('Abstract test ignored\n')
        self.app = None

    def test_example_performance(self):

        # Initialise dict of entities.
        self.entities = {}

        print("{} report:\n".format(type(self).__name__))

        # repetitions = 10
        repetitions = 1

        for i in six.moves.range(0, 4):
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
                for _ in six.moves.range(repetitions):
                    last_n_stored_events = repo.get_most_recent_events(stored_entity_id, limit=n)
                time_last_n = (utc_now() - start_last_n) / repetitions

                num_retrieved_events = len(list(last_n_stored_events))
                events_per_second = num_retrieved_events / time_last_n
                print("Time to get last {} events after {} events: {:.6f}s ({:.0f} events/s)"
                      "".format(n, num_beats + 1, time_last_n, events_per_second))

            last_n(1)
            last_n(10)
            last_n(100)
            last_n(1000)
            last_n(10000)

            # Get the entity by replaying all events (which it must since there isn't a snapshot).
            start_replay = utc_now()
            for _ in six.moves.range(repetitions):
                _ = self.app.example_repo[example.id]
            time_replaying = (utc_now() - start_replay) / repetitions
            print("Time to replay {} beats: {:.2f}s ({:.0f} beats/s, {:.6f}s each)"
                  "".format(num_beats, time_replaying, num_beats / time_replaying, time_replaying / num_beats))

            # Take snapshot, and beat heart a few more times.
            self.app.example_repo.take_snapshot(example.id, until=uuid1().hex)

            extra_beats = 4
            for _ in six.moves.range(extra_beats):
                example.beat_heart()
            num_beats += extra_beats

            # Get the entity using snapshot and replaying events since the snapshot.
            start_replay = utc_now()
            for _ in six.moves.range(repetitions):
                _ = self.app.example_repo[example.id]
            time_replaying = (utc_now() - start_replay) / repetitions

            events_per_second = (extra_beats + 1) / time_replaying  # +1 for the snapshot event
            beats_per_second = num_beats / time_replaying
            print("Time to replay snapshot with {} extra beats: {:.6f}s ({:.0f} events/s, {:.0f} beats/s)"
                  "".format(extra_beats, time_replaying, events_per_second, beats_per_second))
            
            print("")


class TestCassandraPerformance(PerformanceTestCase):

    def setUp(self):
        # Setup the example application.
        self.app = ExampleApplicationWithCassandra()

        # Setup the keyspace and column family for stored events.
        create_cassandra_keyspace_and_tables(DEFAULT_CASSANDRA_KEYSPACE)

    def tearDown(self):
        # Drop the keyspace.
        drop_keyspace(DEFAULT_CASSANDRA_KEYSPACE)

        # Close the application.
        self.app.close()


class TestSQLAlchemyPerformance(PerformanceTestCase):

    def setUp(self):
        # Setup the example application.
        self.app = ExampleApplicationWithSQLAlchemy(db_uri='sqlite:///:memory:')

    def tearDown(self):
        # Close the application.
        self.app.close()


class TestPythonObjectsPerformance(PerformanceTestCase):

    def setUp(self):
        # Setup the example application.
        self.app = ExampleApplicationWithPythonObjects()

    def tearDown(self):
        # Close the application.
        self.app.close()
