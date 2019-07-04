import datetime
import os
import unittest
from time import sleep
from uuid import uuid4

from eventsourcing.application.multiprocess import MultiprocessRunner
from eventsourcing.application.sqlalchemy import SQLAlchemyApplication
from eventsourcing.application.system import MultiThreadedRunner
from eventsourcing.contrib.paxos.application import PaxosSystem, PaxosProcess
from eventsourcing.domain.model.decorators import retry
from eventsourcing.domain.model.events import assert_event_handlers_empty, clear_event_handlers
from eventsourcing.tests.base import notquick
from eventsourcing.tests.test_system_fixtures import set_db_uri


class TestPaxosSystem(unittest.TestCase):

    infrastructure_class = SQLAlchemyApplication

    def test_single_threaded(self):
        # set_db_uri()

        system = PaxosSystem(
            setup_tables=True,
            infrastructure_class=self.infrastructure_class,
        )

        key1, key2, key3 = uuid4(), uuid4(), uuid4()
        value1, value2, value3 = 11111, 22222, 33333

        with system:
            paxosprocess0 = system.processes['paxosprocess0']
            paxosprocess1 = system.processes['paxosprocess1']
            paxosprocess2 = system.processes['paxosprocess2']

            started1 = datetime.datetime.now()
            assert isinstance(paxosprocess0, PaxosProcess)
            paxosprocess0.propose_value(key1, value1)
            ended1 = (datetime.datetime.now() - started1).total_seconds()
            # Check each process has expected final value.
            self.assert_final_value(paxosprocess0, key1, value1)
            self.assert_final_value(paxosprocess1, key1, value1)
            self.assert_final_value(paxosprocess2, key1, value1)
            print("Resolved paxos 1 with single thread in %ss" % ended1)

            started2 = datetime.datetime.now()
            paxosprocess1.propose_value(key2, value2)
            ended2 = (datetime.datetime.now() - started2).total_seconds()
            # Check each process has a resolution.
            self.assert_final_value(paxosprocess0, key2, value2)
            self.assert_final_value(paxosprocess1, key2, value2)
            self.assert_final_value(paxosprocess2, key2, value2)
            print("Resolved paxos 2 with single thread in %ss" % ended2)

            started3 = datetime.datetime.now()
            paxosprocess2.propose_value(key3, value3)
            ended3 = (datetime.datetime.now() - started3).total_seconds()
            # Check each process has a resolution.
            self.assert_final_value(paxosprocess0, key3, value3)
            self.assert_final_value(paxosprocess1, key3, value3)
            self.assert_final_value(paxosprocess2, key3, value3)
            print("Resolved paxos 3 with single thread in %ss" % ended3)

    def test_multi_threaded(self):

        if 'TRAVIS_PYTHON_VERSION' in os.environ:
            if self.infrastructure_class is SQLAlchemyApplication:
                self.skipTest("There's an intermittent problem with the multi-threaded"
                              "runner with SQLAlchemy and Python 3.7 on Travis. Fix me :).")
        set_db_uri()

        system = PaxosSystem(
            setup_tables=True,
            infrastructure_class=self.infrastructure_class,
        )

        key1, key2, key3 = uuid4(), uuid4(), uuid4()
        value1, value2, value3 = 11111, 22222, 33333

        with MultiThreadedRunner(system):
            paxosprocess0 = system.processes['paxosprocess0']
            paxosprocess1 = system.processes['paxosprocess1']
            paxosprocess2 = system.processes['paxosprocess2']

            started1 = datetime.datetime.now()
            assert isinstance(paxosprocess0, PaxosProcess)
            paxosprocess0.propose_value(key1, value1)
            ended1 = (datetime.datetime.now() - started1).total_seconds()
            # Check each process has expected final value.
            self.assert_final_value(paxosprocess0, key1, value1)
            self.assert_final_value(paxosprocess1, key1, value1)
            self.assert_final_value(paxosprocess2, key1, value1)
            print("Resolved paxos 1 with multi threads in %ss" % ended1)

            started2 = datetime.datetime.now()
            paxosprocess1.propose_value(key2, value2)
            ended2 = (datetime.datetime.now() - started2).total_seconds()
            # Check each process has a resolution.
            self.assert_final_value(paxosprocess0, key2, value2)
            self.assert_final_value(paxosprocess1, key2, value2)
            self.assert_final_value(paxosprocess2, key2, value2)
            print("Resolved paxos 2 with multi threads in %ss" % ended2)

            started3 = datetime.datetime.now()
            paxosprocess2.propose_value(key3, value3)
            ended3 = (datetime.datetime.now() - started3).total_seconds()
            # Check each process has a resolution.
            self.assert_final_value(paxosprocess0, key3, value3)
            self.assert_final_value(paxosprocess1, key3, value3)
            self.assert_final_value(paxosprocess2, key3, value3)
            print("Resolved paxos 3 with multi threads in %ss" % ended3)

    def test_multiprocessing(self):
        set_db_uri()

        system = PaxosSystem(
            setup_tables=True,
            infrastructure_class=self.infrastructure_class
        )

        key1, key2, key3 = uuid4(), uuid4(), uuid4()
        value1, value2, value3 = 11111, 22222, 33333

        paxos_process_class = system.process_classes['paxosprocess0']
        paxos_process = system.construct_app(paxos_process_class, pipeline_id=2)
        paxos_process.repository._use_cache = False

        self.close_connections_before_forking()

        pipeline_ids = [1, 2, 3]
        with MultiprocessRunner(system=system, pipeline_ids=pipeline_ids), paxos_process:
            assert isinstance(paxos_process, PaxosProcess)

            sleep(1)
            started1 = datetime.datetime.now()
            paxos_process.propose_value(key1, value1)

            paxos_process.change_pipeline(2)
            started2 = datetime.datetime.now()
            paxos_process.propose_value(key2, value2)

            paxos_process.change_pipeline(3)
            started3 = datetime.datetime.now()
            paxos_process.propose_value(key3, value3)

            self.assert_final_value(paxos_process, key1, value1)
            duration1 = (datetime.datetime.now() - started1).total_seconds()
            print("Resolved paxos 1 with multiprocessing in %ss" % duration1)

            self.assert_final_value(paxos_process, key2, value2)
            duration2 = (datetime.datetime.now() - started2).total_seconds()
            print("Resolved paxos 2 with multiprocessing in %ss" % duration2)

            self.assert_final_value(paxos_process, key3, value3)
            duration3 = (datetime.datetime.now() - started3).total_seconds()
            print("Resolved paxos 3 with multiprocessing in %ss" % duration3)

    @notquick
    def test_multiprocessing_performance(self):

        set_db_uri()

        system = PaxosSystem(
            setup_tables=True,
            infrastructure_class=self.infrastructure_class
        )

        num_pipelines = 1
        pipeline_ids = range(num_pipelines)
        paxos_process_class = system.process_classes['paxosprocess0']

        multiprocess = MultiprocessRunner(system=system, pipeline_ids=pipeline_ids)

        num_proposals = 50

        self.close_connections_before_forking()

        with multiprocess:
            sleep(1)

            paxos_process = system.construct_app(
                process_class=paxos_process_class,
                pipeline_id=pipeline_ids[0]
            )
            assert isinstance(paxos_process, PaxosProcess)
            paxos_process.use_cache = False
            paxos_process.repository._use_cache = False

            with paxos_process:

                started = datetime.datetime.now()

                expectations = list(((uuid4(), i) for i in range(num_proposals)))
                for key, value in expectations:
                    paxos_process.change_pipeline((value % len(pipeline_ids)))
                    print("Proposing key {} value {}".format(key, value))
                    paxos_process.propose_value(key, str(value))
                    sleep(0.0)

                for key, value in expectations:
                    print("Asserting final value for key {} value {}".format(key, value))
                    self.assert_final_value(paxos_process, key, str(value))

                duration = (datetime.datetime.now() - started).total_seconds()
                print(
                    "Resolved {} paxoses with multiprocessing in {:.4f}s ({:.4f}s each)".format(
                        num_proposals, duration, duration / num_proposals
                    )
                )

    @retry((KeyError, AssertionError), max_attempts=100, wait=0.1, stall=0)
    def assert_final_value(self, process, id, value):
        process.repository._cache.clear()
        self.assertEqual(process.repository[id].final_value, value)

    def close_connections_before_forking(self):
        pass

    def tearDown(self):
        try:
            del (os.environ['DB_URI'])
        except KeyError:
            pass
        try:
            assert_event_handlers_empty()
        finally:
            clear_event_handlers()
