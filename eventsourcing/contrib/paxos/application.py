import itertools
from copy import deepcopy
from uuid import UUID

import six
from eventsourcing.application.process import ProcessApplication, ProcessEvent
from eventsourcing.application.system import System
from eventsourcing.contrib.paxos.composable import PaxosInstance, Resolution, PaxosMessage
from eventsourcing.domain.model.aggregate import AggregateRoot
from eventsourcing.domain.model.decorators import attribute
from eventsourcing.exceptions import RepositoryKeyError, ProgrammingError


class PaxosAggregate(AggregateRoot):
    """
    Event-sourced Paxos participant.
    """
    paxos_variables = [
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
    is_verbose = False

    def __init__(self, quorum_size, network_uid, *args, **kwargs):
        assert isinstance(quorum_size, six.integer_types)
        self.quorum_size = quorum_size
        self.network_uid = network_uid
        self.promises_received = set()
        self.nacks_received = set()
        self.leader = False
        self.proposals = {}
        self.acceptors = {}
        self.final_value = None
        self.final_proposal_id = None
        super(PaxosAggregate, self).__init__(*args, **kwargs)

    @property
    def paxos_instance(self):
        """
        Returns instance of PaxosInstance (protocol implementation).
        """
        # Construct instance with the constant attributes.
        instance = PaxosInstance(self.network_uid, self.quorum_size)

        # Set the variable attributes from the aggregate.
        for name in self.paxos_variables:
            value = getattr(self, name, None)
            if value is not None:
                if isinstance(value, (set, list, dict, tuple)):
                    value = deepcopy(value)
                setattr(instance, name, value)

        # Return the instance.
        return instance

    class Event(AggregateRoot.Event):
        """
        Base event class for PaxosAggregate.
        """

    class Started(Event, AggregateRoot.Created):
        """
        Published when a PaxosAggregate is started.
        """
        __notifiable__ = False


    class AttributesChanged(Event):
        """
        Published when attributes of paxos_instance are changed.
        """
        __notifiable__ = False

        def __init__(self, changes=None, **kwargs):
            super(PaxosAggregate.AttributesChanged, self).__init__(
                changes=changes, **kwargs
            )

        @property
        def changes(self):
            return self.__dict__['changes']

        def mutate(self, obj):
            for name, value in self.changes.items():
                setattr(obj, name, value)

    class MessageAnnounced(Event):
        """
        Published when a Paxos message is announced.
        """
        @property
        def msg(self):
            return self.__dict__['msg']

    @classmethod
    def start(cls, originator_id, quorum_size, network_uid):
        """
        Factory method that returns a new Paxos aggregate.
        """
        assert isinstance(quorum_size, six.integer_types), "Not an integer: {}".format(quorum_size)
        return cls.__create__(
            event_class=cls.Started,
            originator_id=originator_id,
            quorum_size=quorum_size,
            network_uid=network_uid
        )

    def propose_value(self, value, assume_leader=False):
        """
        Proposes a value to the network.
        """
        paxos = self.paxos_instance
        paxos.leader = assume_leader
        msg = paxos.propose_value(value)
        if msg is None:
            msg = paxos.prepare()
        self.setattrs_from_paxos(paxos)
        self.announce(msg)
        return msg

    def receive_message(self, msg):
        """
        Responds to messages from other participants.
        """
        paxos = self.paxos_instance
        while msg:
            if isinstance(msg, Resolution):
                self.print_if_verbose("{} resolved value {}".format(self.network_uid, msg.value))
                break
            else:
                self.print_if_verbose("{} <- {} <- {}".format(self.network_uid, msg.__class__.__name__, msg.from_uid))
                msg = paxos.receive(msg)
                if msg:
                    if not isinstance(msg, Resolution):
                        self.announce(msg)

        self.setattrs_from_paxos(paxos)

    def announce(self, msg):
        """
        Announces a Paxos message.
        """
        self.print_if_verbose("{} -> {}".format(self.network_uid, msg.__class__.__name__))
        self.__trigger_event__(
            event_class=self.MessageAnnounced,
            msg=msg,
        )

    def setattrs_from_paxos(self, paxos):
        """
        Registers changes of attribute value on Paxos instance.
        """
        changes = {}
        for name in self.paxos_variables:
            paxos_value = getattr(paxos, name)
            if paxos_value != getattr(self, name, None):
                self.print_if_verbose("{} {}: {}".format(self.network_uid, name, paxos_value))
                changes[name] = paxos_value
                setattr(self, name, paxos_value)
        if changes:
            self.__trigger_event__(
                event_class=self.AttributesChanged,
                changes=changes
            )

    def print_if_verbose(self, param):
        if self.is_verbose:
            print(param)

    def __str__(self):
        return ("PaxosAggregate("
                "network_uid='{network_uid}', "
                "proposal_id='{proposal_id}', "
                "promised_id='{promised_id}', "
                "promises_received='{promises_received}'"
                ")").format(**self.__dict__)


class PaxosProcess(ProcessApplication):
    persist_event_type = PaxosAggregate.Event
    use_cache = True
    quorum_size = None

    def propose_value(self, key, value, assume_leader=False):
        """
        Starts new Paxos aggregate and proposes a value for a key.
        """
        assert isinstance(key, UUID)
        paxos_aggregate = PaxosAggregate.start(
            originator_id=key,
            quorum_size=self.quorum_size,
            network_uid=self.name
        )
        msg = paxos_aggregate.propose_value(value, assume_leader=assume_leader)
        while msg:
            msg = paxos_aggregate.receive_message(msg)
        new_events = paxos_aggregate.__batch_pending_events__()
        self.record_process_event(ProcessEvent(new_events))
        self.repository.take_snapshot(paxos_aggregate.id)
        self.publish_prompt()
        return paxos_aggregate

    def policy(self, repository, event):
        if isinstance(event, PaxosAggregate.MessageAnnounced):
            msg = event.msg
            assert isinstance(msg, PaxosMessage)
            # Get or create aggregate.
            try:
                paxos = repository[event.originator_id]
            except RepositoryKeyError:
                paxos = PaxosAggregate.start(
                    originator_id=event.originator_id,
                    quorum_size=self.quorum_size,
                    network_uid=self.name
                )
                # Needs to go in the cache now, otherwise
                # we get "Duplicate" errors (for some reason).
                self.repository._cache[paxos.id] = paxos
            assert isinstance(paxos, PaxosAggregate), type(paxos)
            # Absolutely make sure the participant aggregates aren't getting confused.
            assert paxos.network_uid == self.name, (
                "Wrong paxos aggregate: required network_uid {}, got {}".format(
                    self.name, paxos.network_uid
                )
            )
            # Only receive messages until resolution is
            # obtained. Followers will process our previous
            # announcements and resolve to the same final value
            # before processing anything we could announce after.
            if not paxos.final_proposal_id:
                paxos.receive_message(msg)

            return paxos
        # else:
        #     raise ProgrammingError(type(event))


class PaxosSystem(System):
    def __init__(self, num_participants=3, **kwargs):
        self.num_participants = num_participants
        self.quorum_size = (num_participants + 2) // 2
        classes = [
            type(
                'PaxosProcess{}'.format(i),
                (PaxosProcess,),
                {'quorum_size': self.quorum_size}
            ) for i in range(num_participants)
        ]
        if num_participants > 1:
            pipelines = [[c[0], c[1], c[0]] for c in itertools.combinations(classes, 2)]
        else:
            pipelines = [classes]
        super(PaxosSystem, self).__init__(*pipelines, **kwargs)
