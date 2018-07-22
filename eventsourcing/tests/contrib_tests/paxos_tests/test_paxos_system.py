import datetime
import os
import unittest
from time import sleep

from eventsourcing.application.multiprocess import Multiprocess
from eventsourcing.application.sqlalchemy import WithSQLAlchemy
from eventsourcing.contrib.paxos.application import PaxosSystem
from eventsourcing.domain.model.events import assert_event_handlers_empty
from eventsourcing.tests.test_system_fixtures import set_db_uri


class TestPaxosSystem(unittest.TestCase):

    process_class = WithSQLAlchemy

    def test_single_threaded(self):
        system = PaxosSystem(setup_tables=True, num_participants=3, process_class=self.process_class)

        with system:
            paxosprocess0 = system.processes['paxosprocess0']
            paxosprocess1 = system.processes['paxosprocess1']
            paxosprocess2 = system.processes['paxosprocess2']
            paxos1 = paxosprocess0.propose_value(11111, quorum_size=system.quorum_size, assume_leader=False)
            paxos2 = paxosprocess1.propose_value(22222, quorum_size=system.quorum_size, assume_leader=False)
            paxos3 = paxosprocess2.propose_value(33333, quorum_size=system.quorum_size, assume_leader=False)

            # Check each process has a resolution.
            self.assertEqual(paxosprocess0.repository[paxos1.id].resolution.value, 11111)
            self.assertEqual(paxosprocess1.repository[paxos1.id].resolution.value, 11111)
            self.assertEqual(paxosprocess2.repository[paxos1.id].resolution.value, 11111)
            self.assertEqual(paxosprocess0.repository[paxos2.id].resolution.value, 22222)
            self.assertEqual(paxosprocess1.repository[paxos2.id].resolution.value, 22222)
            self.assertEqual(paxosprocess2.repository[paxos2.id].resolution.value, 22222)
            self.assertEqual(paxosprocess0.repository[paxos3.id].resolution.value, 33333)
            self.assertEqual(paxosprocess1.repository[paxos3.id].resolution.value, 33333)
            self.assertEqual(paxosprocess2.repository[paxos3.id].resolution.value, 33333)

        # system.drop_tables()

    def close_connections_before_forking(self):
        pass

    def test_multiprocessing(self):
        set_db_uri()

        system = PaxosSystem(setup_tables=True, num_participants=3, process_class=self.process_class)

        paxos_process_class = system.process_classes['PaxosProcess0']
        paxos_process = system.construct_app(paxos_process_class, pipeline_id=1)

        self.close_connections_before_forking()

        with Multiprocess(system, pipeline_ids=[1, 2, 3]), paxos_process as paxosprocess0:
            sleep(3)
            print("Running {}".format(datetime.datetime.now()))
            paxos1 = paxosprocess0.propose_value(11111, quorum_size=system.quorum_size, assume_leader=True)

            paxosprocess0.change_pipeline(2)
            paxos2 = paxosprocess0.propose_value(22222, quorum_size=system.quorum_size, assume_leader=True)

            paxosprocess0.change_pipeline(3)
            paxos3 = paxosprocess0.propose_value(33333, quorum_size=system.quorum_size, assume_leader=True)

            # Check each process has a resolution.
            while True:
                if paxosprocess0.repository[paxos1.id].resolution:
                    break
            self.assertEqual(paxosprocess0.repository[paxos1.id].resolution.value, 11111)
            print("")
            print("")
            print("")
            print("")
            print("Finished {}".format(datetime.datetime.now()))

            while True:
                if paxosprocess0.repository[paxos2.id].resolution:
                    break
            self.assertEqual(paxosprocess0.repository[paxos2.id].resolution.value, 22222)

            while True:
                if paxosprocess0.repository[paxos3.id].resolution:
                    break
            self.assertEqual(paxosprocess0.repository[paxos3.id].resolution.value, 33333)

        system.drop_tables()


    def tearDown(self):
        assert_event_handlers_empty()

        try:
            del (os.environ['DB_URI'])
        except KeyError:
            pass
