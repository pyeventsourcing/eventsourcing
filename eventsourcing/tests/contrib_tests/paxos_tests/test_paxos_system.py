import datetime
import os
import unittest
from time import sleep
from uuid import uuid4

from eventsourcing.application.multiprocess import Multiprocess
from eventsourcing.application.sqlalchemy import SQLAlchemyApplication
from eventsourcing.contrib.paxos.application import PaxosSystem, PaxosProcess, PaxosAggregate
from eventsourcing.domain.model.events import assert_event_handlers_empty, clear_event_handlers
from eventsourcing.tests.test_system_fixtures import set_db_uri

PaxosAggregate.is_verbose = False

class TestPaxosSystem(unittest.TestCase):

    infrastructure_class = SQLAlchemyApplication

    def test_single_threaded(self):
        system = PaxosSystem(setup_tables=True, num_participants=3, infrastructure_class=self.infrastructure_class)

        key1, key2, key3 = uuid4(), uuid4(), uuid4()
        value1, value2, value3 = 11111, 22222, 33333

        with system:
            paxosprocess0 = system.processes['paxosprocess0']
            paxosprocess1 = system.processes['paxosprocess1']
            paxosprocess2 = system.processes['paxosprocess2']
            started = datetime.datetime.now()

            paxos1 = paxosprocess0.propose_value(key1, value1,
                                                 quorum_size=system.quorum_size,
                                                 assume_leader=False)
            print("Resolved with single thread in %ss" % (datetime.datetime.now() - started).total_seconds())
            started = datetime.datetime.now()
            paxos2 = paxosprocess1.propose_value(key2, value2,
                                                 quorum_size=system.quorum_size,
                                                 assume_leader=False)
            print("Resolved with single thread in %ss" % (datetime.datetime.now() - started).total_seconds())
            started = datetime.datetime.now()
            paxos3 = paxosprocess2.propose_value(key3, value3,
                                                 quorum_size=system.quorum_size,
                                                 assume_leader=False)
            print("Resolved with single thread in %ss" % (datetime.datetime.now() - started).total_seconds())

            # Check each process has a resolution.
            self.assertEqual(paxosprocess0.repository[paxos1.id].resolution.value, value1)
            self.assertEqual(paxosprocess1.repository[paxos1.id].resolution.value, value1)
            self.assertEqual(paxosprocess2.repository[paxos1.id].resolution.value, value1)
            self.assertEqual(paxosprocess0.repository[paxos2.id].resolution.value, value2)
            self.assertEqual(paxosprocess1.repository[paxos2.id].resolution.value, value2)
            self.assertEqual(paxosprocess2.repository[paxos2.id].resolution.value, value2)
            self.assertEqual(paxosprocess0.repository[paxos3.id].resolution.value, value3)
            self.assertEqual(paxosprocess1.repository[paxos3.id].resolution.value, value3)
            self.assertEqual(paxosprocess2.repository[paxos3.id].resolution.value, value3)

        # system.drop_tables()

    def close_connections_before_forking(self):
        pass

    def test_multiprocessing(self):
        set_db_uri()

        system = PaxosSystem(setup_tables=True, num_participants=3, infrastructure_class=self.infrastructure_class)

        key1, key2, key3 = uuid4(), uuid4(), uuid4()
        value1, value2, value3 = 11111, 22222, 33333

        paxos_process_class = system.process_classes['PaxosProcess0']
        paxos_process = system.construct_app(paxos_process_class, pipeline_id=1)

        self.close_connections_before_forking()

        with Multiprocess(system, pipeline_ids=[1, 2, 3]), paxos_process as paxosprocess0:
            sleep(3)
            started = datetime.datetime.now()
            paxos1 = paxosprocess0.propose_value(key1, value1,
                                                 quorum_size=system.quorum_size,
                                                 assume_leader=True)

            paxosprocess0.change_pipeline(2)
            paxos2 = paxosprocess0.propose_value(key2, value2,
                                                 quorum_size=system.quorum_size,
                                                 assume_leader=True)

            paxosprocess0.change_pipeline(3)
            paxos3 = paxosprocess0.propose_value(key3, value3,
                                                 quorum_size=system.quorum_size,
                                                 assume_leader=True)

            # Check each process has a resolution.
            while not paxosprocess0.repository[paxos1.id].resolution:
                sleep(0.1)
            self.assertEqual(paxosprocess0.repository[paxos1.id].resolution.value, value1)
            print("Resolved with multiprocessing in %ss" % (datetime.datetime.now() - started).total_seconds())

            while not paxosprocess0.repository[paxos2.id].resolution:
                sleep(0.1)
            self.assertEqual(paxosprocess0.repository[paxos2.id].resolution.value, value2)

            while not paxosprocess0.repository[paxos3.id].resolution:
                sleep(0.1)
            self.assertEqual(paxosprocess0.repository[paxos3.id].resolution.value, value3)

        # system.drop_tables()

    def tearDown(self):
        try:
            del (os.environ['DB_URI'])
        except KeyError:
            pass
        try:
            assert_event_handlers_empty()
        finally:
            clear_event_handlers()
