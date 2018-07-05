"""
This module provides an implementation of the Paxos algorithm as
a set of composable classes.

Copied, with minor alterations for use with Python 3 and JSON from
https://github.com/cocagne/python-composable-paxos

The MIT License (MIT)

Copyright (c) 2015 Tom Cocagne

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

# ProposalID
#
# In order for the Paxos algorithm to function, all proposal ids must be
# unique. A simple way to ensure this is to include the proposer's unique
# id in the proposal id.
#
# Python tuples allow the proposal number and the UID to be combined in a
# manner that supports comparison in the expected manner:
#
#   (4,'C') > (4,'B') > (3,'Z')
#
# Named tuples from the collections module support all of the regular
# tuple operations but additionally allow access to the contents by
# name so the numeric component of the proposal ID may be referred to
# via 'proposal_id.number' instead of 'proposal_id[0]'.
#
# ProposalID = collections.namedtuple('ProposalID', ['number', 'uid'])

# Replaced ProposalID class, because json package turns namedtuples into a list.


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
        return 'ProposalID(number={}, uid="{}")'.format(self.number, self.uid)

    def __hash__(self):
        return hash((self.number, self.uid))


class PaxosMessage(object):
    '''
    Base class for all messages defined in this module
    '''
    from_uid = None  # Set by subclass constructor


class Prepare(PaxosMessage):
    '''
    Prepare messages should be broadcast to all Acceptors.
    '''

    def __init__(self, from_uid, proposal_id):
        self.from_uid = from_uid
        self.proposal_id = proposal_id


class Nack(PaxosMessage):
    '''
    NACKs are technically optional though few practical applications will
    want to omit their use. They are used to signal a proposer that their
    current proposal number is out of date and that a new one should be
    chosen. NACKs may be sent in response to both Prepare and Accept
    messages
    '''

    def __init__(self, from_uid, proposer_uid, proposal_id, promised_proposal_id):
        self.from_uid = from_uid
        self.proposal_id = proposal_id
        self.proposer_uid = proposer_uid
        self.promised_proposal_id = promised_proposal_id


class Promise(PaxosMessage):
    '''
    Promise messages should be sent to at least the Proposer specified in
    the proposer_uid field
    '''

    def __init__(self, from_uid, proposer_uid, proposal_id, last_accepted_id, last_accepted_value):
        self.from_uid = from_uid
        self.proposer_uid = proposer_uid
        self.proposal_id = proposal_id
        self.last_accepted_id = last_accepted_id
        self.last_accepted_value = last_accepted_value


class Accept(PaxosMessage):
    '''
    Accept messages should be broadcast to all Acceptors
    '''

    def __init__(self, from_uid, proposal_id, proposal_value):
        self.from_uid = from_uid
        self.proposal_id = proposal_id
        self.proposal_value = proposal_value


class Accepted(PaxosMessage):
    '''
    Accepted messages should be sent to all Learners
    '''

    def __init__(self, from_uid, proposal_id, proposal_value):
        self.from_uid = from_uid
        self.proposal_id = proposal_id
        self.proposal_value = proposal_value


class Resolution(PaxosMessage):
    '''
    Optional message used to indicate that the final value has been selected
    '''

    def __init__(self, from_uid, value):
        self.from_uid = from_uid
        self.value = value


class InvalidMessageError(Exception):
    '''
    Thrown if a PaxosMessage subclass is passed to a class that does not
    support it
    '''


class MessageHandler(object):

    def receive(self, msg):
        '''
        Message dispatching function. This function accepts any PaxosMessage subclass and calls
        the appropriate handler function
        '''
        handler = getattr(self, 'receive_' + msg.__class__.__name__.lower(), None)
        if handler is None:
            raise InvalidMessageError('Receiving class does not support messages of type: ' + msg.__class__.__name__)
        return handler(msg)


class Proposer(MessageHandler):
    '''
    The 'leader' attribute is a boolean value indicating the Proposer's
    belief in whether or not it is the current leader. This is not a reliable
    value as multiple nodes may simultaneously believe themselves to be the
    leader.
    '''

    leader = False
    proposed_value = None
    proposal_id = None
    highest_accepted_id = None
    promises_received = None
    nacks_received = None
    current_prepare_msg = None
    current_accept_msg = None

    def __init__(self, network_uid, quorum_size):
        self.network_uid = network_uid
        self.quorum_size = quorum_size
        self.proposal_id = ProposalID(0, network_uid)
        self.highest_proposal_id = ProposalID(0, network_uid)

    def propose_value(self, value):
        '''
        Sets the proposal value for this node iff this node is not already aware of
        a previous proposal value. If the node additionally believes itself to be
        the current leader, an Accept message will be returned
        '''
        if self.proposed_value is None:
            self.proposed_value = value

            if self.leader:
                self.current_accept_msg = Accept(self.network_uid, self.proposal_id, value)
                return self.current_accept_msg

    def prepare(self):
        '''
        Returns a new Prepare message with a proposal id higher than
        that of any observed proposals. A side effect of this method is
        to clear the leader flag if it is currently set.
        '''

        self.leader = False
        self.promises_received = set()
        self.nacks_received = set()
        self.proposal_id = ProposalID(self.highest_proposal_id.number + 1, self.network_uid)
        self.highest_proposal_id = self.proposal_id
        self.current_prepare_msg = Prepare(self.network_uid, self.proposal_id)

        return self.current_prepare_msg

    def observe_proposal(self, proposal_id):
        '''
        Optional method used to update the proposal counter as proposals are
        seen on the network.  When co-located with Acceptors and/or Learners,
        this method may be used to avoid a message delay when attempting to
        assume leadership (guaranteed NACK if the proposal number is too low).
        This method is automatically called for all received Promise and Nack
        messages.
        '''
        if proposal_id > self.highest_proposal_id:
            self.highest_proposal_id = proposal_id

    def receive_nack(self, msg):
        '''
        Returns a new Prepare message if the number of Nacks received reaches
        a quorum.
        '''
        self.observe_proposal(msg.promised_proposal_id)

        if msg.proposal_id == self.proposal_id and self.nacks_received is not None:
            self.nacks_received.add(msg.from_uid)

            if len(self.nacks_received) == self.quorum_size:
                return self.prepare()  # Lost leadership or failed to acquire it

    def receive_promise(self, msg):
        '''
        Returns an Accept messages if a quorum of Promise messages is achieved
        '''
        self.observe_proposal(msg.proposal_id)

        if not self.leader and msg.proposal_id == self.proposal_id and msg.from_uid not in self.promises_received:

            self.promises_received.add(msg.from_uid)

            if self.highest_accepted_id is None or msg.last_accepted_id > self.highest_accepted_id:
                self.highest_accepted_id = msg.last_accepted_id
                if msg.last_accepted_value is not None:
                    self.proposed_value = msg.last_accepted_value

            if len(self.promises_received) == self.quorum_size:
                self.leader = True

                if self.proposed_value is not None:
                    self.current_accept_msg = Accept(self.network_uid, self.proposal_id, self.proposed_value)
                    return self.current_accept_msg


class Acceptor(MessageHandler):
    '''
    Acceptors act as the fault-tolerant memory for Paxos. To ensure correctness
    in the presense of failure, Acceptors must be able to remember the promises
    they've made even in the event of power outages. Consequently, any changes
    to the promised_id, accepted_id, and/or accepted_value must be persisted to
    stable media prior to sending promise and accepted messages.

    When an Acceptor instance is composed alongside a Proposer instance, it
    is generally advantageous to call the proposer's observe_proposal()
    method when methods of this class are called.
    '''

    def __init__(self, network_uid, promised_id=None, accepted_id=None, accepted_value=None):
        '''
        promised_id, accepted_id, and accepted_value should be provided if and only if this
        instance is recovering from persistent state.
        '''
        self.network_uid = network_uid
        self.promised_id = promised_id
        self.accepted_id = accepted_id
        self.accepted_value = accepted_value

    def receive_prepare(self, msg):
        '''
        Returns either a Promise or a Nack in response. The Acceptor's state must be persisted to disk
        prior to transmitting the Promise message.
        '''
        if self.promised_id is None or msg.proposal_id >= self.promised_id:
            self.promised_id = msg.proposal_id
            return Promise(self.network_uid, msg.from_uid, self.promised_id, self.accepted_id, self.accepted_value)
        else:
            return Nack(self.network_uid, msg.from_uid, msg.proposal_id, self.promised_id)

    def receive_accept(self, msg):
        '''
        Returns either an Accepted or Nack message in response. The Acceptor's state must be persisted
        to disk prior to transmitting the Accepted message.
        '''
        if self.promised_id is None or msg.proposal_id >= self.promised_id:
            self.promised_id = msg.proposal_id
            self.accepted_id = msg.proposal_id
            self.accepted_value = msg.proposal_value
            return Accepted(self.network_uid, msg.proposal_id, msg.proposal_value)
        else:
            return Nack(self.network_uid, msg.from_uid, msg.proposal_id, self.promised_id)


class ProposalStatus(object):
    __slots__ = ['accept_count', 'retain_count', 'acceptors', 'value']

    def __init__(self, value):
        self.accept_count = 0
        self.retain_count = 0
        self.acceptors = set()
        self.value = value


class Learner(MessageHandler):
    '''
    This class listens to Accepted messages, determines when the final value is
    selected, and tracks which peers have accepted the final value.
    '''

    def __init__(self, network_uid, quorum_size):
        self.network_uid = network_uid
        self.quorum_size = quorum_size
        self.proposals = dict()  # maps proposal_id => ProposalStatus
        self.acceptors = dict()  # maps from_uid => last_accepted_proposal_id
        self.final_value = None
        self.final_acceptors = None  # Will be a set of acceptor UIDs once the final value is chosen
        self.final_proposal_id = None

    def receive_accepted(self, msg):
        '''
        Called when an Accepted message is received from an acceptor. Once the final value
        is determined, the return value of this method will be a Resolution message containing
        the consentual value. Subsequent calls after the resolution is chosen will continue to add
        new Acceptors to the final_acceptors set and return Resolution messages.
        '''
        if self.final_value is not None:
            if msg.proposal_id >= self.final_proposal_id and msg.proposal_value == self.final_value:
                self.final_acceptors.add(msg.from_uid)
            return Resolution(self.network_uid, self.final_value)

        last_pn = self.acceptors.get(msg.from_uid)

        if last_pn is not None and msg.proposal_id <= last_pn:
            return  # Old message

        self.acceptors[msg.from_uid] = msg.proposal_id

        if last_pn is not None:
            # String proposal_key, need string keys for JSON.
            proposal_key = str(last_pn)
            ps = self.proposals[proposal_key]
            ps.retain_count -= 1
            ps.acceptors.remove(msg.from_uid)
            if ps.retain_count == 0:
                del self.proposals[proposal_key]

        # String proposal_key, need string keys for JSON.
        proposal_key = str(msg.proposal_id)
        if not proposal_key in self.proposals:
            self.proposals[proposal_key] = ProposalStatus(msg.proposal_value)

        ps = self.proposals[proposal_key]

        assert msg.proposal_value == ps.value, 'Value mismatch for single proposal!'

        ps.accept_count += 1
        ps.retain_count += 1
        ps.acceptors.add(msg.from_uid)

        if ps.accept_count == self.quorum_size:
            self.final_proposal_id = msg.proposal_id
            self.final_value = msg.proposal_value
            self.final_acceptors = ps.acceptors
            self.proposals = None
            self.acceptors = None

            return Resolution(self.network_uid, self.final_value)


class PaxosInstance(Proposer, Acceptor, Learner):
    '''
    Aggregate Proposer, Accepter, & Learner class.
    '''

    def __init__(self, network_uid, quorum_size, promised_id=None, accepted_id=None, accepted_value=None):
        Proposer.__init__(self, network_uid, quorum_size)
        Acceptor.__init__(self, network_uid, promised_id, accepted_id, accepted_value)
        Learner.__init__(self, network_uid, quorum_size)

    def receive_prepare(self, msg):
        self.observe_proposal(msg.proposal_id)
        return super(PaxosInstance, self).receive_prepare(msg)

    def receive_accept(self, msg):
        self.observe_proposal(msg.proposal_id)
        return super(PaxosInstance, self).receive_accept(msg)
