import itertools
from copy import deepcopy
from uuid import uuid4

import six
from eventsourcing.application.sqlalchemy import ProcessApplicationWithSnapshotting
from eventsourcing.application.system import System
from eventsourcing.contrib.paxos.composable import PaxosInstance, Resolution, PaxosMessage
from eventsourcing.domain.model.aggregate import AggregateRoot
from eventsourcing.domain.model.decorators import attribute


class PaxosAggregate(AggregateRoot):
    def __init__(self, quorum_size, network_uid, *args, **kwargs):
        assert isinstance(quorum_size, six.integer_types)
        self.quorum_size = quorum_size
        self.network_uid = network_uid
        self.promises_received = set()
        self.nacks_received = set()
        self.leader = False
        self.proposals = {}
        self.acceptors = {}
        # self.resolution = None
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
            value = getattr(self, attr, None)
            if value is not None:
                if isinstance(value, (set, list, dict, tuple)):
                    value = deepcopy(value)
                setattr(instance, attr, value)

        return instance

    @attribute
    def resolution(self):
        pass

    class Event(AggregateRoot.Event):
        pass

    class Started(Event, AggregateRoot.Created):
        pass

    class AttributesChanged(Event):
        __notifiable__ = False

        def __init__(self, changes=None, **kwargs):
            super(PaxosAggregate.AttributesChanged, self).__init__(
                changes=changes, **kwargs
            )

        @property
        def changes(self):
            return self.__dict__['changes']

        def mutate(self, obj):
            for attr, value in self.changes.items():
                setattr(obj, attr, value)

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

    def propose_value(self, value, assume_leader=False):
        paxos = self.paxos
        paxos.leader = assume_leader
        msg = paxos.propose_value(value)
        if msg is None:
            msg = paxos.prepare()
        self.setattrs_from_paxos(paxos)
        self.announce(msg)
        return msg

    def receive_message(self, msg):
        paxos = self.paxos
        while msg:

            if isinstance(msg, Resolution):
                if self.resolution is None:
                    print("{} resolved value {}".format(self.network_uid, msg.value))
                    self.resolution = msg
                break
            else:
                print("{} <- {} <- {}".format(self.network_uid, msg.__class__.__name__, msg.from_uid))
                msg = paxos.receive(msg)
                if msg:
                    if not isinstance(msg, Resolution):
                        self.announce(msg)

        self.setattrs_from_paxos(paxos)

    def announce(self, msg):
        print("{} -> {}".format(self.network_uid, msg.__class__.__name__))

        self.__trigger_event__(
            event_class=self.MessageAnnounced,
            msg=msg,
        )

    def setattrs_from_paxos(self, paxos):
        changes = {}
        for attr in self.paxos_attrs:
            paxos_value = getattr(paxos, attr)
            if paxos_value != getattr(self, attr, None):
                print("{} {}: {}".format(self.network_uid, attr, paxos_value))
                changes[attr] = paxos_value
                setattr(self, attr, paxos_value)
        if changes:
            self.__trigger_event__(
                event_class=self.AttributesChanged,
                changes=changes
            )


class PaxosProcess(ProcessApplicationWithSnapshotting):
    always_track_notifications = True
    snapshot_period = None
    persist_event_type = PaxosAggregate.Event

    def propose_value(self, value, quorum_size, assume_leader=False):
        paxos = PaxosAggregate.start(
            originator_id=uuid4(),
            quorum_size=quorum_size,
            network_uid=self.name
        )
        msg = paxos.propose_value(value, assume_leader=assume_leader)
        while msg:
            msg = paxos.receive_message(msg)
        self.record_new_events(paxos)
        self.publish_prompt()
        self.repository.take_snapshot(paxos.id)
        return paxos

    def policy(self, repository, event):
        # print("Running policy for {}".format(self.name))
        if isinstance(event, PaxosAggregate.Started):
            if event.originator_id not in repository:
                return PaxosAggregate.start(
                    originator_id=event.originator_id,
                    quorum_size=event.quorum_size,
                    network_uid=self.name
                )
        elif isinstance(event, PaxosAggregate.MessageAnnounced):
            msg = event.msg
            assert isinstance(msg, PaxosMessage)
            paxos = repository[event.originator_id]
            assert isinstance(paxos, PaxosAggregate)
            if not paxos.resolution:
                paxos.receive_message(msg)
                self.repository.take_snapshot(paxos.id)


class PaxosSystem(System):
    def __init__(self, processes=3, **kwargs):
        classes = [type('PaxosProcess{}'.format(i), (PaxosProcess,), {}) for i in range(processes)]
        if processes > 1:
            pipelines = [[c[0], c[1], c[0]] for c in itertools.combinations(classes, 2)]
        else:
            pipelines = [classes]
        self.quorum_size = (processes + 2) // 2
        super(PaxosSystem, self).__init__(*pipelines, **kwargs)
