from uuid import UUID, uuid5, uuid4

from eventsourcing.domain.model.sequence import Sequence, SequenceRepository, CompoundSequenceRepository, \
    CompoundSequence, start_compound_sequence
from eventsourcing.exceptions import ConcurrencyError, SequenceFullError
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
from eventsourcing.infrastructure.sequencereader import SequenceReader, CompoundSequenceReader


class SequenceRepo(EventSourcedRepository, SequenceRepository):
    mutator = Sequence._mutate

    def get_entity(self, entity_id, lt=None, lte=None):
        """
        Replays entity using only the 'Started' event.
        
        :rtype: Sequence
        """
        return self.event_player.replay_entity(entity_id, limit=1)

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

    def get_reader(self, sequence_id, i, j, h, max_size):
        """
        Returns a sequence reader for the given sequence_id.
        
        Starts sequence entity if it doesn't exist.
        
        :rtype: SequenceReader 
        """
        return CompoundSequenceReader(
            sequence=self.get_or_create(sequence_id, i, j, h, max_size),
            event_store=self.event_store,
        )

    def create_sequence_id(self, ns, i, j):
        sequence_id = uuid5(ns, str((i, j)))
        print('Created sequence ID: {}, {}, {}, {}'.format(ns, i, j, sequence_id))
        return sequence_id

    def start(self, ns, i, j, h, max_size):
        sequence_id = self.create_sequence_id(ns, i, j)

        try:
            sequence = start_compound_sequence(sequence_id, i=i, j=j, h=h, max_size=max_size)
        except ConcurrencyError as e:
            raise
            # raise Exception("Can't start compound sequence, ns={}, i={}, j={}: {}".format(ns, i, j, e))

        return CompoundSequenceReader(sequence, self.event_store)

    def start_root(self, max_size):
        sequence_id = uuid4()
        sequence = start_compound_sequence(sequence_id, i=None, j=None, h=None, max_size=max_size)
        return CompoundSequenceReader(sequence, self.event_store)

    def get_last_sequence(self, sequence):
        try:
            last = sequence[-1]
        except IndexError:
            return sequence
        else:
            if isinstance(last, UUID):
                s = CompoundSequenceReader(self[last], self.event_store)
                return self.get_last_sequence(s)
            else:
                return sequence

    def get_last_item(self, sequence):
        last_sequence = self.get_last_sequence(sequence)
        return last_sequence[-1]

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

    def calc_parent_i_j_h(self, child):
        N = child.max_size
        c_i = child.i
        c_j = child.j
        c_h = child.h
        c_n = c_i // (N ** c_h)
        p_n = c_n // N
        p_h = c_h + 1
        p_width = N ** p_h
        p_i = p_n * p_width
        p_j = p_i + p_width
        if p_i > c_i:
            raise AssertionError(p_i, c_i)
        if p_j < c_j:
            raise AssertionError(p_j, c_j)
        return p_i, p_j, p_h

    def create_detached_branch(self, ns, child, max_height):
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

    def attach_branch(self, parent_id, branch_id):
        sequence = self[parent_id]
        parent = CompoundSequenceReader(sequence, self.event_store)
        parent.append(branch_id)

    def append_item(self, item, sequence_id):
        root = CompoundSequenceReader(self[sequence_id], self.event_store)
        last = self.get_last_sequence(root)
        try:
            last.append(item)
        except SequenceFullError:
            next = self.extend_base(root.id, last, item)
            detached, target_id = self.create_detached_branch(root.id, next, len(root))
            top_id = root[-1]
            if target_id:
                self.attach_branch(target_id, detached.id)
            else:
                self.demote(root, self[top_id], detached.id)

    def start_root_with_item(self, max_size, item):
        root = self.start_root(max_size)
        i = 0
        j = max_size
        child1 = self.start(root.id, i, j, 1, max_size=root.max_size)
        root.append(child1.id)
        child1.append(item)
        return root
