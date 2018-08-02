import datetime
import os
import unittest
from time import sleep
from uuid import uuid4

from eventsourcing.application.multiprocess import Multiprocess
from eventsourcing.application.sqlalchemy import SQLAlchemyApplication
from eventsourcing.contrib.paxos.application import PaxosSystem, PaxosProcess
from eventsourcing.domain.model.decorators import retry
from eventsourcing.domain.model.events import assert_event_handlers_empty, clear_event_handlers
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
            sleep(0.1)

    def test_multiprocessing(self):
        set_db_uri()

        system = PaxosSystem(
            setup_tables=True,
            infrastructure_class=self.infrastructure_class
        )

        key1, key2, key3 = uuid4(), uuid4(), uuid4()
        value1, value2, value3 = 11111, 22222, 33333

        paxos_process_class = system.process_classes['PaxosProcess0']
        paxos_process = system.construct_app(paxos_process_class, pipeline_id=2)
        paxos_process.repository._use_cache = False

        self.close_connections_before_forking()

        pipeline_ids = [1, 2, 3]
        with Multiprocess(system=system, pipeline_ids=pipeline_ids), paxos_process:
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


    @retry((KeyError, AssertionError), max_attempts=200, wait=0.05, stall=0.1)
    def assert_final_value(self, process, id, value):
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
