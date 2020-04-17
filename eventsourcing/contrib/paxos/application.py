import itertools
from copy import deepcopy
from typing import Any, Dict, Optional, Sequence, Set, Union
from uuid import UUID

from eventsourcing.application.process import ProcessApplication, WrappedRepository
from eventsourcing.contrib.paxos.composable import (
    PaxosInstance,
    PaxosMessage,
    ProposalStatus,
    Resolution,
)
from eventsourcing.domain.model.aggregate import BaseAggregateRoot
from eventsourcing.domain.model.decorators import retry
from eventsourcing.exceptions import (
    OperationalError,
    RecordConflictError,
    RepositoryKeyError,
)
from eventsourcing.system.definition import System


class PaxosAggregate(BaseAggregateRoot):
    """
    Event-sourced Paxos participant.
    """

    paxos_variables = [
        "proposed_value",
        "proposal_id",
        "promised_id",
        "accepted_id",
        "accepted_value",
        "highest_proposal_id",
        "promises_received",
        "nacks_received",
        "highest_accepted_id",
        "leader",
        "proposals",
        "acceptors",
        "final_value",
    ]
    is_verbose = False

    def __init__(self, quorum_size: int, network_uid: str, **kwargs: Any):
        assert isinstance(quorum_size, int)
        self.quorum_size = quorum_size
        self.network_uid = network_uid
        self.promises_received: Set[str] = set()
        self.nacks_received: Set[str] = set()
        self.leader = False
        self.proposals: Dict[str, ProposalStatus] = {}
        self.acceptors: Dict[str, str] = {}
        self.final_value = None
        super(PaxosAggregate, self).__init__(**kwargs)

    @property
    def paxos_instance(self) -> PaxosInstance:
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

    class Event(BaseAggregateRoot.Event["PaxosAggregate"]):
        """
        Base event class for PaxosAggregate.
        """

    class Started(Event, BaseAggregateRoot.Created["PaxosAggregate"]):
        """
        Published when a PaxosAggregate is started.
        """

        __notifiable__ = False

    class AttributesChanged(Event):
        """
        Published when attributes of paxos_instance are changed.
        """

        __notifiable__ = False

        def __init__(self, changes: Optional[Dict[str, Any]] = None, **kwargs: Any):
            super(PaxosAggregate.AttributesChanged, self).__init__(
                changes=changes, **kwargs
            )

        @property
        def changes(self) -> Dict[str, Any]:
            return self.__dict__["changes"]

        def mutate(self, obj: "PaxosAggregate") -> None:
            for name, value in self.changes.items():
                setattr(obj, name, value)

    @classmethod
    def start(
        cls, originator_id: UUID, quorum_size: int, network_uid: str
    ) -> "PaxosAggregate":
        """
        Factory method that returns a new Paxos aggregate.
        """
        assert isinstance(quorum_size, int), "Not an integer: {}".format(quorum_size)
        started_class = cls.Started
        return cls.__create__(
            originator_id=originator_id,
            event_class=started_class,
            quorum_size=quorum_size,
            network_uid=network_uid,
        )

    def propose_value(self, value: Any, assume_leader: bool = False) -> PaxosMessage:
        """
        Proposes a value to the network.
        """
        if value is None:
            raise ValueError("Not allowed to propose value None")
        paxos = self.paxos_instance
        paxos.leader = assume_leader
        msg = paxos.propose_value(value)
        if msg is None:
            msg = paxos.prepare()
        self.setattrs_from_paxos(paxos)
        self.announce(msg)
        return msg

    def receive_message(self, msg: PaxosMessage) -> None:
        """
        Responds to messages from other participants.
        """
        if isinstance(msg, Resolution):
            return
        paxos = self.paxos_instance
        while msg:
            if isinstance(msg, Resolution):
                self.print_if_verbose(
                    "{} resolved value {}".format(self.network_uid, msg.value)
                )
                break
            else:
                self.print_if_verbose(
                    "{} <- {} <- {}".format(
                        self.network_uid, msg.__class__.__name__, msg.from_uid
                    )
                )
                msg = paxos.receive(msg)
                # Todo: Make it optional not to announce resolution
                #  (without which it's hard to see final value).
                do_announce_resolution = True
                if msg and (do_announce_resolution or not isinstance(msg, Resolution)):
                    self.announce(msg)

        self.setattrs_from_paxos(paxos)

    def announce(self, msg: PaxosMessage) -> None:
        """
        Announces a Paxos message.
        """
        self.print_if_verbose(
            "{} -> {}".format(self.network_uid, msg.__class__.__name__)
        )
        self.__trigger_event__(event_class=self.MessageAnnounced, msg=msg)

    class MessageAnnounced(Event):
        """
        Published when a Paxos message is announced.
        """

        @property
        def msg(self) -> PaxosMessage:
            return self.__dict__["msg"]

    def setattrs_from_paxos(self, paxos: PaxosInstance) -> None:
        """
        Registers changes of attribute value on Paxos instance.
        """
        changes = {}
        for name in self.paxos_variables:
            paxos_value = getattr(paxos, name)
            if paxos_value != getattr(self, name, None):
                self.print_if_verbose(
                    "{} {}: {}".format(self.network_uid, name, paxos_value)
                )
                changes[name] = paxos_value
                setattr(self, name, paxos_value)
        if changes:
            self.__trigger_event__(event_class=self.AttributesChanged, changes=changes)

    def print_if_verbose(self, param: Any) -> None:
        if self.is_verbose:
            print(param)

    def __str__(self) -> str:
        return (
            "PaxosAggregate("
            "final_value='{final_value}', "
            "proposed_value='{proposed_value}', "
            "network_uid='{network_uid}', "
            "proposal_id='{proposal_id}', "
            "promised_id='{promised_id}', "
            "promises_received='{promises_received}'"
            ")"
        ).format(**self.__dict__)


class PaxosApplication(ProcessApplication[PaxosAggregate, PaxosAggregate.Event]):
    persist_event_type = PaxosAggregate.Event
    quorum_size: int = 0
    notification_log_section_size = 5
    use_cache = True
    set_notification_ids = True

    @retry((RecordConflictError, OperationalError), max_attempts=10, wait=0)
    def propose_value(
        self, key: UUID, value: Any, assume_leader: bool = False
    ) -> PaxosAggregate:
        """
        Starts new Paxos aggregate and proposes a value for a key.

        Decorated with retry in case of notification log conflict
        or operational error.

        This a good example of writing process event from an
        application command. Just get the batch of pending events
        and record a process event with those events alone. They
        will be written atomically.
        """
        assert self.quorum_size > 0
        assert isinstance(key, UUID)
        paxos_aggregate = PaxosAggregate.start(
            originator_id=key, quorum_size=self.quorum_size, network_uid=self.name
        )
        msg = paxos_aggregate.propose_value(value, assume_leader=assume_leader)
        paxos_aggregate.receive_message(msg)

        self.save(paxos_aggregate)

        return paxos_aggregate  # in case it's new

    def get_final_value(self, key: UUID) -> PaxosAggregate:
        return self.repository[key].final_value

    def policy(
        self,
        repository: WrappedRepository[PaxosAggregate, PaxosAggregate.Event],
        event: PaxosAggregate.Event,
    ) -> Optional[Union[PaxosAggregate, Sequence[PaxosAggregate]]]:
        """
        Processes paxos "message announced" events of other applications
        by starting or continuing a paxos aggregate in this application.
        """
        if isinstance(event, PaxosAggregate.MessageAnnounced):
            # Get or create aggregate.
            try:
                paxos = repository[event.originator_id]
            except RepositoryKeyError:
                paxos = PaxosAggregate.start(
                    originator_id=event.originator_id,
                    quorum_size=self.quorum_size,
                    network_uid=self.name,
                )
                # Needs to go in the cache now, otherwise we get
                # "Duplicate" errors (for some unknown reason).
                if self.repository.use_cache:
                    self.repository.put_entity_in_cache(paxos.id, paxos)
            # Absolutely make sure the participant aggregates aren't getting confused.
            assert (
                paxos.network_uid == self.name
            ), "Wrong paxos aggregate: required network_uid {}, got {}".format(
                self.name, paxos.network_uid
            )
            # Only receive messages until resolution is
            # obtained. Followers will process our previous
            # announcements and resolve to the same final value
            # before processing anything we could announce after.
            msg = event.msg
            assert isinstance(msg, PaxosMessage)
            if paxos.final_value is None:
                paxos.receive_message(msg)

            return paxos
        else:
            return None


class PaxosSystem(System):
    def __init__(self, num_participants: int = 3, **kwargs: Any):
        self.num_participants = num_participants
        self.quorum_size = (num_participants + 2) // 2
        classes = [
            type(
                "PaxosApplication{}".format(i),
                (PaxosApplication,),
                {"quorum_size": self.quorum_size},
            )
            for i in range(num_participants)
        ]
        if num_participants > 1:
            pipelines = [[c[0], c[1], c[0]] for c in itertools.combinations(classes, 2)]
        else:
            pipelines = [classes]
        super(PaxosSystem, self).__init__(*pipelines, **kwargs)
