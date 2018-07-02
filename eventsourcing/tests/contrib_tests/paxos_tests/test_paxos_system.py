import itertools
import unittest
from copy import deepcopy
from uuid import uuid4

import composable_paxos
import six
from composable_paxos import PaxosInstance, Resolution

from eventsourcing.application.sqlalchemy import ProcessApplication
from eventsourcing.application.system import System
from eventsourcing.domain.model.aggregate import AggregateRoot
from eventsourcing.domain.model.decorators import attribute
from eventsourcing.tests.test_system_fixtures import set_db_uri


class ProposalID(object):
    def __init__(self, number, uid):
        self.number = number
        self.uid = uid

    def __gt__(self, other):
        if other is None:
            return True
        elif isinstance(other, ProposalID):
            return (self.number, self.uid) > (other.number, other.uid)
        elif isinstance(other, list):
            return [self.number, self.uid] > other

    def __ge__(self, other):
        if other is None:
            return True
        elif isinstance(other, ProposalID):
            return (self.number, self.uid) >= (other.number, other.uid)
        elif isinstance(other, list):
            return [self.number, self.uid] >= other

    def __eq__(self, other):
        if other is None:
            return False
        elif isinstance(other, ProposalID):
            return (self.number, self.uid) == (other.number, other.uid)
        elif isinstance(other, list):
            return [self.number, self.uid] == other

    def __repr__(self):
        return 'ProposalID(number={}, uid="{}"'.format(self.number, self.uid)

    def __hash__(self):
        return hash((self.number, self.uid))


composable_paxos.ProposalID = ProposalID


class Paxos(AggregateRoot):
    def __init__(self, quorum_size, network_uid, *args, **kwargs):
        assert isinstance(quorum_size, six.integer_types)
        self.quorum_size = quorum_size
        self.network_uid = network_uid
        super(AggregateRoot, self).__init__(*args, **kwargs)

    paxos_attrs = [
        'proposed_value',
        'proposal_id',
        'promised_id',
        'accepted_id',
        'accepted_value',
        'highest_proposal_id',
        'promises_received',
        'nacks_received',
        'highest_accepted_id',
        'leader',
        'proposals',
        'acceptors',
        'final_value',
        'final_acceptors',
        'final_proposal_id',
    ]

    @property
    def paxos(self):
        instance = PaxosInstance(
            network_uid=self.network_uid,
            quorum_size=self.quorum_size,
        )

        for attr in self.paxos_attrs:
            value = getattr(self, attr)
            if value is not None:
                if isinstance(value, (set, list, dict, tuple)):
                    value = deepcopy(value)
                setattr(instance, attr, value)

        return instance

    @attribute
    def proposal_id(self):
        pass

    @attribute
    def highest_proposal_id(self):
        pass

    @attribute
    def promises_received(self):
        pass

    @attribute
    def nacks_received(self):
        pass

    @attribute
    def highest_accepted_id(self):
        pass

    @attribute
    def leader(self):
        pass

    @attribute
    def proposed_value(self):
        pass

    @attribute
    def proposed_value(self):
        pass

    @attribute
    def proposals(self):
        pass

    @attribute
    def acceptors(self):
        pass

    @attribute
    def final_value(self):
        pass

    @attribute
    def final_acceptors(self):
        pass

    @attribute
    def final_proposal_id(self):
        pass

    @attribute
    def promised_id(self):
        pass

    @attribute
    def accepted_id(self):
        pass

    @attribute
    def accepted_value(self):
        pass

    @attribute
    def resolution(self):
        pass


    class Event(AggregateRoot.Event):
        pass

    class Started(Event, AggregateRoot.Created):
        pass

    class AttributeChanged(Event, AggregateRoot.AttributeChanged):
        pass

    class MessageAnnounced(Event):
        @property
        def msg(self):
            return self.__dict__['msg']

    @classmethod
    def start(cls, originator_id, quorum_size, network_uid):
        assert isinstance(quorum_size, six.integer_types), "Not an integer: {}".format(quorum_size)
        return cls.__create__(
            event_class=cls.Started,
            originator_id=originator_id,
            quorum_size=quorum_size,
            network_uid=network_uid
        )

    def propose_value(self, value):
        paxos = self.paxos
        msg = paxos.propose_value(value)
        if msg is None:
            msg = paxos.prepare()
        self.setattrs_from_paxos(paxos)
        self.announce(msg)

    def receive_message(self, event):
        paxos = self.paxos
        if isinstance(event.msg, Resolution):
            pass
            if event.msg != self.resolution:
                self.resolution = event.msg

        else:
            msg = paxos.receive(event.msg)
            print(msg)
            self.setattrs_from_paxos(paxos)
            if msg is not None:
                self.announce(msg)
            if isinstance(msg, Resolution):
                self.resolution = msg

    def announce(self, msg):
        self.__trigger_event__(
            event_class=self.MessageAnnounced,
            msg=msg,
        )

    def setattrs_from_paxos(self, paxos):
        for attr in self.paxos_attrs:
            paxos_value = getattr(paxos, attr)
            if paxos_value != getattr(self, attr):
                setattr(self, attr, paxos_value)


class PaxosProcess(ProcessApplication):
    def policy(self, repository, event):
        if isinstance(event, Paxos.Started):
            if event.originator_id not in repository:
                return Paxos.start(
                    originator_id=event.originator_id,
                    quorum_size=event.quorum_size,
                    network_uid=self.name
                )
        elif isinstance(event, Paxos.MessageAnnounced):
            consensus = repository[event.originator_id]
            assert isinstance(consensus, Paxos)
            consensus.receive_message(event)


class PaxosSystem(System):
    def __init__(self, processes=3, **kwargs):
        classes = [type('PaxosProcess{}'.format(i), (PaxosProcess,), {}) for i in range(processes)]
        pipelines = [c[0] | c[1] | c[0] for c in itertools.combinations(classes, 2)]
        self.quorum_size = (processes + 2) // 2
        super(PaxosSystem, self).__init__(*pipelines, **kwargs)


class TestPaxosSystem(unittest.TestCase):

    def test(self):
        set_db_uri()
        system = PaxosSystem(setup_tables=True)

        paxos_process0 = PaxosProcess(name='paxosprocess0', persist_event_type=Paxos.Event, setup_tables=True)
        with paxos_process0:
            paxos = Paxos.start(
                originator_id=uuid4(),
                quorum_size=system.quorum_size,
                network_uid='paxosprocess0'
            )
            paxos.propose_value(11111)
            paxos.__save__()

        # paxos_process1 = PaxosProcess(name='paxosprocess0', persist_event_type=Paxos.Event, setup_tables=True)
        # with paxos_process1:
        #     paxos = paxos_process1.repository[paxos.id]
        #     paxos.propose_value(22222)
        #     paxos.__save__()

        with system:
            # Prompt again (it's single threaded).
            system.paxosprocess0.publish_prompt()

            # Check the consensus has been registered with each application in the system.
            assert paxos.id in system.paxosprocess0.repository
            assert paxos.id in system.paxosprocess1.repository
            assert paxos.id in system.paxosprocess2.repository

            self.assertEqual(paxos_process0.repository[paxos.id].resolution.value, 11111)
            self.assertEqual(system.paxosprocess1.repository[paxos.id].resolution.value, 11111)
            self.assertEqual(system.paxosprocess2.repository[paxos.id].resolution.value, 11111)
