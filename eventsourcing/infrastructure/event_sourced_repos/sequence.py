from uuid import uuid4, uuid5

from eventsourcing.domain.model.decorators import retry
from eventsourcing.domain.model.sequence import CompoundSequence, CompoundSequenceRepository, Sequence, \
    SequenceRepository, start_compound_sequence
from eventsourcing.exceptions import ConcurrencyError, SequenceFullError
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
from eventsourcing.infrastructure.sequencereader import CompoundSequenceReader, SequenceReader


class SequenceRepo(EventSourcedRepository, SequenceRepository):
    mutator = Sequence._mutate

    def get_entity(self, entity_id, lt=None, lte=None):
        """
        Replays entity using only the 'Started' event.
        
        :rtype: Sequence
        """
        return self.event_player.replay_entity(entity_id, limit=1)

    # Todo: Factor this out?
    def get_reader(self, sequence_id, max_size=None):
        """
        Returns a sequence reader for the given sequence_id.
        
        Starts sequence entity if it doesn't exist.
        
        :rtype: SequenceReader 
        """
        return SequenceReader(
            sequence=self.get_or_create(sequence_id, max_size=max_size),
            event_store=self.event_store,
        )


class CompoundSequenceRepo(EventSourcedRepository, CompoundSequenceRepository):
    mutator = CompoundSequence._mutate

    def get_entity(self, entity_id, lt=None, lte=None):
        """
        Replays entity using only the 'Started' event.
        
        :rtype: Sequence
        """
        return self.event_player.replay_entity(entity_id, limit=1)

    def start_root(self, max_size):
        # Create root entity.
        sequence_id = uuid4()
        sequence = start_compound_sequence(sequence_id, i=None, j=None, h=None, max_size=max_size)
        root = CompoundSequenceReader(sequence, self.event_store)
        # Add first sequence to root.
        child = self.start(ns=root.id, i=0, j=root.max_size, h=1, max_size=root.max_size)
        root.append(child.id)
        # Return root.
        return root

    @retry(ConcurrencyError, max_retries=20, wait=0)
    def append_item(self, item, sequence_id):
        root = CompoundSequenceReader(self[sequence_id], self.event_store)
        last = self.get_last_sequence(root)
        try:
            last.append(item)
        except SequenceFullError as e:
            if root.max_size == 1:
                raise e
            # This may raise a ConcurrencyError, if another
            # thread has just extended the compound.
            # If so, just let the exception be caught by
            # the retry decorator, so a fresh attempt is
            # made to append the item to the compound sequence.
            next = self.extend_base(root.id, last, item)

            # If we managed to extend the base, then create a
            # branch. No other thread should be attempting this.
            # So if it fails, the compound will need to be repaired.
            detached_branch, target_id = self.create_detached_branch(root.id, next, len(root))

            # If there is a target, then attach the branch to it.
            if target_id:
                self.attach_branch(target_id, detached_branch)
            # Otherwise demote the top in favour of the branch.
            else:
                top_id = root[-1]
                self.demote(root, self[top_id], detached_branch.id)

    def get_last_item(self, sequence):
        last_sequence = self.get_last_sequence(sequence)
        return last_sequence[-1]

    def get_last_sequence(self, sequence):
        # Root must have a sequence.
        if sequence.h is None:
            sequence = sequence[-1]

        # Descend into the compound.
        while sequence.h > 1:
            sequence = sequence[-1]

        # Return a reader.
        return CompoundSequenceReader(sequence, self.event_store)

    def start(self, ns, i, j, h, max_size):
        sequence_id = self.create_sequence_id(ns, i, j)
        sequence = start_compound_sequence(sequence_id, i=i, j=j, h=h, max_size=max_size)
        return CompoundSequenceReader(sequence, self.event_store)

    def demote(self, root, child, detached_id=None):
        i = 0  # always zero, because always demote the apex
        j = child.j * child.max_size  # N**h
        h = child.h + 1
        new_child = self.start(root.id, i, j, h, max_size=child.max_size)
        # First, append child to new child.
        new_child.append(child.id)
        # Attach new branch.
        if detached_id is not None:
            new_child.append(detached_id)
        # Then append new child to to root.
        root.append(new_child.id)
        return new_child

    def extend_base(self, ns, left, item):
        i = left.j
        j = i + left.max_size
        h = left.h
        new = self.start(ns, i, j, h, max_size=left.max_size)
        # Append an item to new child.
        new.append(item)

        return new

    def create_detached_branch(self, ns, child, max_height):
        """
        Works up from child, attempting to create a parent,
        until it conflicts with already existing sequence,
        when it stops and returns what it has created.
        """
        target_id = None
        while True:
            i, j, h = self.calc_parent_i_j_h(child)
            if h > max_height:
                break
            sequence_id = self.create_sequence_id(ns, i, j)
            try:
                parent = start_compound_sequence(sequence_id, i, j, h, child.max_size)
            except ConcurrencyError:
                # It already exists.
                target_id = sequence_id
                break
            else:
                reader = CompoundSequenceReader(parent, self.event_store)
                reader.append(child.id)
                child = reader
        return child, target_id

    def attach_branch(self, parent_id, branch):
        sequence = self[parent_id]
        parent = CompoundSequenceReader(sequence, self.event_store)
        # If the calculations are correct, this won't ever raise a ConcurrencyError.
        parent.append(branch.id)

    def calc_parent_i_j_h(self, child):
        N = child.max_size
        c_i = child.i
        c_j = child.j
        c_h = child.h
        # Calculate the number of the sequence in its row (sequences
        # with same height), from left to right, starting from 0.
        c_n = c_i // (N ** c_h)
        p_n = c_n // N
        # Parent height is child height plus one.
        p_h = c_h + 1
        # Span of sequences in parent row is max size N, to the power of the height.
        span = N ** p_h
        # Calculate parent i and j.
        p_i = p_n * span
        p_j = p_i + span
        # Check the parent i,j bounds the child i,j.
        if p_i > c_i:
            raise AssertionError(p_i, c_i)
        if p_j < c_j:
            raise AssertionError(p_j, c_j)
        # Return parent i, j, h.
        return p_i, p_j, p_h

    def create_sequence_id(self, ns, i, j):
        return uuid5(ns, str((i, j)))
